"""
data/foundation/leverage_index_builder.py

Build a static leverage-index table from historical game state→outcome data.

LI = (avg win-prob swing from this state)^2 / (mean win-prob swing squared overall).
We use squared swing so high-leverage states (big potential swings either way)
rank above states that are effectively locked.

Output schema: inning (1-12), outs (0-2), base_state (0-7), score_bucket (-5..+5),
              leverage_index (float, normalized to mean=1.0)
"""
from __future__ import annotations
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/features/leverage_index.parquet")


def _score_bucket(score_diff: int) -> int:
    """Clamp score_diff to [-5, 5]."""
    return max(-5, min(5, int(score_diff)))


def build_leverage_table(pa_wp_swings: pd.DataFrame) -> pd.DataFrame:
    """
    pa_wp_swings columns: inning (int), outs (int), base_state (int),
                          score_diff (int), wp_swing_sq (float)
    Returns one row per (inning, outs, base_state, score_bucket) with normalized LI.
    """
    cols = ["inning", "outs", "base_state", "score_bucket", "leverage_index"]
    if pa_wp_swings.empty:
        return pd.DataFrame(columns=cols)

    df = pa_wp_swings.copy()
    df["score_bucket"] = df["score_diff"].apply(_score_bucket)
    grouped = df.groupby(
        ["inning", "outs", "base_state", "score_bucket"]
    )["wp_swing_sq"].mean().reset_index()
    overall_mean = float(grouped["wp_swing_sq"].mean())
    if overall_mean <= 0:
        grouped["leverage_index"] = 1.0
    else:
        grouped["leverage_index"] = grouped["wp_swing_sq"] / overall_mean
    return grouped[cols]


def build_from_snapshots(snapshots_dir: Path = Path("data/features")) -> pd.DataFrame:
    """
    Derive PA-level WP swings from snapshot history.

    For each (inning, outs, base_state, score_diff) bin, compute empirical
    home-win rate and use variance = p*(1-p) as proxy for WP swing squared
    (uncertainty peaks at p=0.5).
    """
    parquets = sorted(snapshots_dir.glob("snapshots_*.parquet"))
    if not parquets:
        raise FileNotFoundError(f"No snapshot parquets in {snapshots_dir}")
    frames = []
    for p in parquets:
        df = pd.read_parquet(p, columns=["inning", "outs", "base_state",
                                         "score_diff", "home_won_final"])
        frames.append(df)
    snaps = pd.concat(frames, ignore_index=True)

    snaps["score_bucket"] = snaps["score_diff"].apply(_score_bucket)
    g = snaps.groupby(
        ["inning", "outs", "base_state", "score_bucket"]
    )["home_won_final"].agg(["mean", "size"]).reset_index()
    g["wp_swing_sq"] = g["mean"] * (1 - g["mean"])
    # Filter low-sample bins (noisy)
    g = g[g["size"] >= 20]

    pa = g.rename(columns={"score_bucket": "score_diff"})[
        ["inning", "outs", "base_state", "score_diff", "wp_swing_sq"]]
    return build_leverage_table(pa)


def main() -> None:
    df = build_from_snapshots()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
