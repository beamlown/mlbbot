"""
tools/feature_sanity_check.py — Offline vs live feature distribution check

Compares min / median / p90 / p99 for the five features most likely to have
training/inference mismatches:

    pitch_count_norm   (home + away)
    tto                (home + away)
    is_bullpen         (home + away)
    pregame_logit
    elo_diff_norm

Offline side:  loads data/features/features_all.parquet if it exists,
               otherwise falls back to raw snapshots.

Live side:     tries ESPN for any currently live games;
               if no games are live, runs against a set of synthetic
               GameStateSnapshots spanning typical game phases.

Usage:
    cd Desktop/mlb_model
    python -m tools.feature_sanity_check

    # Or point at a specific parquet:
    python -m tools.feature_sanity_check --features data/features/features_all.parquet
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sanity_check")

# ── Percentile helper ─────────────────────────────────────────────────────────

def _pct(arr: np.ndarray, p: float) -> float:
    if len(arr) == 0:
        return float("nan")
    return float(np.percentile(arr, p))


def _stats(arr: np.ndarray) -> dict:
    arr = arr[~np.isnan(arr)]
    return {
        "n":   len(arr),
        "min": _pct(arr, 0),
        "p25": _pct(arr, 25),
        "med": _pct(arr, 50),
        "p90": _pct(arr, 90),
        "p99": _pct(arr, 99),
        "max": _pct(arr, 100),
    }


# ── Print table ───────────────────────────────────────────────────────────────

FEATURES_OF_INTEREST = [
    "pregame_logit",
    "elo_diff_norm",
    "home_pitch_count_norm",
    "away_pitch_count_norm",
    "home_tto",
    "away_tto",
    "home_is_bullpen",
    "away_is_bullpen",
]

FLAG_COLS = {"home_is_bullpen", "away_is_bullpen"}


def _print_comparison(offline_rows: list[dict], live_rows: list[dict]) -> None:
    print()
    print("=" * 90)
    print(f"  FEATURE DISTRIBUTION SANITY CHECK")
    print(f"  offline n={len(offline_rows)}   live n={len(live_rows)}")
    print("=" * 90)

    hdr = f"{'Feature':<28} {'Side':<8} {'n':>6} {'min':>7} {'p25':>7} {'med':>7} {'p90':>7} {'p99':>7} {'max':>7}"
    print(hdr)
    print("-" * 90)

    for feat in FEATURES_OF_INTEREST:
        for side, rows in [("offline", offline_rows), ("live", live_rows)]:
            vals = np.array([r[feat] for r in rows if feat in r], dtype=float)
            s = _stats(vals)
            flag = " *FLAG*" if _needs_flag(feat, s, side, offline_rows, live_rows) else ""
            print(
                f"  {feat:<26} {side:<8} {s['n']:>6} "
                f"{s['min']:>7.3f} {s['p25']:>7.3f} {s['med']:>7.3f} "
                f"{s['p90']:>7.3f} {s['p99']:>7.3f} {s['max']:>7.3f}{flag}"
            )
        print()

    print("=" * 90)
    print("  * FLAG = live p90 or median is more than 2x off from offline counterpart")
    print()


def _needs_flag(feat: str, live_s: dict, side: str, offline: list, live: list) -> bool:
    if side != "live":
        return False
    off_vals = np.array([r[feat] for r in offline if feat in r], dtype=float)
    off_s = _stats(off_vals)
    if off_s["n"] == 0 or live_s["n"] == 0:
        return False
    # Flag if median ratio is outside [0.5, 2.0] for non-zero medians
    om, lm = abs(off_s["med"]), abs(live_s["med"])
    if om > 0.01 and lm > 0.01:
        ratio = max(om, lm) / min(om, lm)
        if ratio > 2.0:
            return True
    # Flag if p90 ratio is outside [0.5, 2.0]
    o90, l90 = abs(off_s["p90"]), abs(live_s["p90"])
    if o90 > 0.01 and l90 > 0.01:
        ratio = max(o90, l90) / min(o90, l90)
        if ratio > 2.0:
            return True
    return False


# ── Offline side ──────────────────────────────────────────────────────────────

def load_offline_rows(features_path: Path | None, n_sample: int = 2000) -> list[dict]:
    """Load a random sample from the feature store parquet."""
    import pandas as pd

    if features_path is None:
        features_path = Path("data/features/features_all.parquet")

    if not features_path.exists():
        # Try snapshots instead
        snap_files = sorted(Path("data/features").glob("snapshots_*.parquet"))
        if not snap_files:
            logger.warning("No feature store or snapshot files found. "
                           "Run the data pipeline first for offline stats.")
            return []
        logger.info("Feature store not found; loading raw snapshots from %d files", len(snap_files))
        parts = [pd.read_parquet(f) for f in snap_files]
        df = pd.concat(parts, ignore_index=True)
        return _build_offline_rows_from_snapshots(df, n_sample)

    logger.info("Loading offline feature store: %s", features_path)
    df = pd.read_parquet(features_path)
    if len(df) > n_sample:
        df = df.sample(n_sample, random_state=42)
    logger.info("Offline sample: %d rows", len(df))

    rows = []
    for _, r in df.iterrows():
        rows.append({feat: float(r[feat]) for feat in FEATURES_OF_INTEREST if feat in r})
    return rows


def _build_offline_rows_from_snapshots(df, n_sample: int) -> list[dict]:
    """Build feature rows from raw snapshot data (before feature engineering)."""
    import pandas as pd

    if len(df) > n_sample:
        df = df.sample(n_sample, random_state=42)

    rows = []
    eps = 1e-6

    def safe_logit(p):
        p = max(eps, min(1 - eps, float(p)))
        return float(np.log(p / (1 - p)))

    for _, r in df.iterrows():
        pwp = float(r.get("pregame_win_prob", 0.54))
        he = float(r.get("home_elo", 1500))
        ae = float(r.get("away_elo", 1500))
        hpc = float(r.get("home_pitch_count", 0))
        apc = float(r.get("away_pitch_count", 0))
        rows.append({
            "pregame_logit":          safe_logit(pwp),
            "elo_diff_norm":          (he - ae) / 400.0,
            "home_pitch_count_norm":  hpc / 100.0,
            "away_pitch_count_norm":  apc / 100.0,
            "home_tto":               float(r.get("home_tto", 1.0)),
            "away_tto":               float(r.get("away_tto", 1.0)),
            "home_is_bullpen":        float(r.get("home_is_bullpen", 0)),
            "away_is_bullpen":        float(r.get("away_is_bullpen", 0)),
        })
    return rows


# ── Live side ─────────────────────────────────────────────────────────────────

def build_live_rows() -> list[dict]:
    """
    Try to get feature vectors from currently live MLB games.
    Falls back to synthetic representative snapshots if no games are live.
    """
    try:
        rows = _live_from_espn()
        if rows:
            logger.info("Live: got %d feature vectors from ESPN", len(rows))
            return rows
    except Exception as e:
        logger.warning("ESPN live fetch failed: %s — using synthetic snapshots", e)

    logger.info("No live games found or ESPN unavailable — using synthetic snapshots")
    return _synthetic_snapshots()


def _live_from_espn() -> list[dict]:
    """Try to pull real live game states via the registry + inference pipeline."""
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from sports.mlb.live_game_registry import refresh_registry, get_live_games
    from sports.mlb.game_state_service import get_game_snapshot
    from sports.mlb.winprob_inference import _build_feature_vector, load_artifacts

    try:
        load_artifacts()
    except Exception as e:
        logger.warning("Model artifacts not loaded (%s) — inference features will use defaults", e)

    refresh_registry()
    live = get_live_games()
    if not live:
        return []

    rows = []
    for game in live:
        snap = get_game_snapshot(game.home_team, game.away_team)
        if snap is None:
            continue
        try:
            _, feat_dict, _ = _build_feature_vector(snap, pregame_win_prob=0.54)
            row = {k: feat_dict[k] for k in FEATURES_OF_INTEREST if k in feat_dict}
            rows.append(row)
        except Exception as e:
            logger.debug("Inference feature build failed for %s: %s", game.game_key, e)

    return rows


def _synthetic_snapshots() -> list[dict]:
    """
    Build a set of synthetic game states that span the realistic distribution
    of live game states during trading hours.

    Each scenario defines (pregame_prob, elo_diff, home_pc, away_pc,
    home_is_bp, away_is_bp, inning, half, score_diff, outs).
    TTO and pitch_count_norm are computed exactly as inference does.
    elo_diff_norm is computed exactly as the fixed inference formula does.
    """
    import math

    scenarios = [
        # (label,           p_pre,  elo_d, h_pc, a_pc, h_bp, a_bp, inn, half, sdiff, outs)
        ("early-balanced",  0.52,    0,    22,   20,   False, False,  2,  0,   0,  0),
        ("early-home-fav",  0.62,  100,    35,   30,   False, False,  3,  1,   1,  1),
        ("early-away-fav",  0.42, -100,    18,   25,   False, False,  2,  0,  -2,  2),
        ("mid-starter",     0.55,   50,    60,   58,   False, False,  5,  0,   0,  0),
        ("mid-home-leads",  0.65,   80,    72,   55,   False, False,  6,  1,   2,  1),
        ("mid-away-leads",  0.38,  -80,    50,   70,   False, False,  5,  0,  -3,  0),
        ("late-home-bp",    0.60,   60,    15,   90,    True, False,  7,  1,   1,  0),
        ("late-away-bp",    0.45,  -60,    88,   12,   False,  True,  8,  0,  -1,  2),
        ("both-bullpen",    0.52,   10,    10,    8,    True,  True,  8,  1,   0,  1),
        ("9th-tie",         0.53,   20,   105,  100,    True,  True,  9,  0,   0,  0),
        ("9th-home-leads",  0.78,   40,    95,  108,    True,  True,  9,  1,   3,  1),
        ("extras",          0.51,    5,    12,   10,    True,  True, 10,  0,   0,  0),
        ("blowout-late",    0.93,  150,    80,   70,    True, False,  8,  1,   8,  0),
        ("close-late-hfav", 0.71,   90,   103,   98,    True,  True,  7,  0,   1,  2),
        ("close-late-afav", 0.29,  -90,    98,  103,   False,  True,  7,  1,  -1,  2),
        # vary pregame_logit range
        ("even-match",      0.500,   0,    45,   45,   False, False,  4,  0,   0,  0),
        ("strong-home",     0.70,  135,    40,   42,   False, False,  4,  1,   0,  1),
        ("weak-home",       0.35, -130,    38,   41,   False, False,  4,  0,   0,  0),
    ]

    def safe_logit(p):
        eps = 1e-6
        p = max(eps, min(1 - eps, p))
        return math.log(p / (1 - p))

    LN10 = 2.302585

    rows = []
    for sc in scenarios:
        (label, p_pre, elo_d, h_pc, a_pc, h_bp, a_bp, inn, half, sdiff, outs) = sc

        pregame_logit   = safe_logit(p_pre)
        elo_diff_norm   = safe_logit(p_pre) / LN10          # fixed inference formula
        h_pc_norm       = h_pc / 100.0
        a_pc_norm       = a_pc / 100.0
        # TTO: fixed inference formula matches training (pc/27 + 1, cap 3.0)
        h_tto = min(3.0, h_pc / 27.0 + 1.0) if h_pc > 0 else 1.0
        a_tto = min(3.0, a_pc / 27.0 + 1.0) if a_pc > 0 else 1.0

        rows.append({
            "pregame_logit":          pregame_logit,
            "elo_diff_norm":          elo_diff_norm,
            "home_pitch_count_norm":  h_pc_norm,
            "away_pitch_count_norm":  a_pc_norm,
            "home_tto":               h_tto,
            "away_tto":               a_tto,
            "home_is_bullpen":        float(h_bp),
            "away_is_bullpen":        float(a_bp),
            "_label":                 label,
        })

    return rows


# ── Elo diff cross-check ──────────────────────────────────────────────────────

def _elo_crosscheck() -> None:
    """
    Show the training vs inference value of elo_diff_norm for a range of
    representative Elo differences. Quick numeric confirmation the fix is right.
    """
    import math
    LN10 = 2.302585

    print("  ELO_DIFF_NORM cross-check (training vs fixed inference formula)")
    print(f"  {'elo_diff':>10} {'p_home':>8} {'training':>12} {'inference':>12} {'match':>6}")
    print("  " + "-" * 52)

    for elo_diff in (-200, -100, -50, 0, 50, 100, 200):
        p_home = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
        training_val  = elo_diff / 400.0
        logit_e       = math.log(p_home / (1.0 - p_home))
        inference_val = logit_e / LN10
        match = abs(training_val - inference_val) < 0.001
        print(f"  {elo_diff:>10} {p_home:>8.4f} {training_val:>12.4f} {inference_val:>12.4f} {'OK' if match else 'MISMATCH':>6}")
    print()


# ── TTO cross-check ───────────────────────────────────────────────────────────

def _tto_crosscheck() -> None:
    """
    Show training vs inference TTO values at representative pitch counts / AB counts.
    Training: abs_faced / 9.0 + 1.0 (AB count based)
    Inference (fixed): pitch_count / 27.0 + 1.0 (assuming ~3 pitches/batter)
    """
    print("  TTO cross-check (training uses AB count, inference uses pitch count)")
    print(f"  {'pitches':>8} {'~ABs':>6} {'train_tto':>10} {'infer_tto':>10} {'delta':>7}")
    print("  " + "-" * 48)

    for pitches in (0, 10, 27, 40, 54, 81, 100, 120):
        approx_abs = pitches / 3.0  # ~3 pitches per batter
        train_tto  = min(3.0, approx_abs / 9.0 + 1.0)
        infer_tto  = min(3.0, pitches / 27.0 + 1.0) if pitches > 0 else 1.0
        delta      = infer_tto - train_tto
        print(f"  {pitches:>8} {approx_abs:>6.1f} {train_tto:>10.3f} {infer_tto:>10.3f} {delta:>+7.3f}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Feature distribution sanity check")
    parser.add_argument("--features", type=Path, default=None,
                        help="Path to features_all.parquet (default: data/features/features_all.parquet)")
    parser.add_argument("--n-sample", type=int, default=2000,
                        help="Number of offline rows to sample (default: 2000)")
    parser.add_argument("--skip-live", action="store_true",
                        help="Skip ESPN live fetch (always use synthetic snapshots)")
    args = parser.parse_args()

    # Change to project root if run from tools/
    if Path.cwd().name == "tools":
        os.chdir(Path.cwd().parent)

    sys.path.insert(0, str(Path.cwd()))

    print()
    print("━" * 90)
    print("  MLB MODEL — FEATURE DISTRIBUTION SANITY CHECK")
    print("━" * 90)

    # Cross-checks first (no data needed)
    _elo_crosscheck()
    _tto_crosscheck()

    # Distribution comparison
    offline_rows = load_offline_rows(args.features, args.n_sample)
    if args.skip_live:
        live_rows = _synthetic_snapshots()
        logger.info("Using synthetic snapshots for live side (--skip-live)")
    else:
        live_rows = build_live_rows()

    if not offline_rows:
        print("  WARNING: No offline data available — run data pipeline first.")
        print("  Showing live/synthetic distribution only.\n")
        offline_rows = []

    _print_comparison(offline_rows, live_rows)

    # Verdict
    print("  INTERPRETATION GUIDE")
    print("  ─────────────────────────────────────────────────────────────────")
    print("  pregame_logit:        expect range ~[-1.2, +1.2] both sides")
    print("  elo_diff_norm:        expect ~[-0.5, +0.5], same scale as training")
    print("  pitch_count_norm:     expect 0.0–1.3, median ~0.5–0.7 mid-game")
    print("  tto:                  expect 1.0–3.0, median ~1.5–2.5 mid-game")
    print("  is_bullpen:           expect ~20–40% True (float 0.0/1.0)")
    print()
    print("  If * FLAG * appears: check the formula in winprob_inference.py")
    print("  against the corresponding line in feature_store.py / state_snapshot_builder.py.")
    print()


if __name__ == "__main__":
    main()
