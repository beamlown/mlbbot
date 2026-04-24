"""
tools/replay_harness.py
Counterfactual replay: re-evaluate historical closed trades against alternative
guardrail configurations to estimate gate effectiveness before going live.

Limitations
-----------
* OB data (spread, depth, imbalance, ask/bid) is not stored in trades_sports.db.
  The harness reconstructs a synthetic OBSnapshot from entry_px that will pass
  all OB-dependent gates. Gate accuracy is therefore highest for fields that
  ARE stored: confidence, entry_px (price-range gates).
* MAX_TOTAL_COMMITTED_USD is always forced to 0.0 in replay mode to bypass the
  live-DB exposure query.
* SL-cooldown state is reset between runs; cluster analysis uses reason_close.

Usage (from sports_bot_v2/ directory)
--------------------------------------
  python tools/replay_harness.py
  python tools/replay_harness.py --config '{"MIN_ENTRY_CONFIDENCE": 0.65}'
  python tools/replay_harness.py --preset tighter_confidence
  python tools/replay_harness.py --all-presets
  python tools/replay_harness.py --db trades_sports_archive_20260404.db
  python tools/replay_harness.py --json-out
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from typing import Any

# Make sports_bot_v2/ root importable as 'core.*'
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── Stub types matching core/types.py interface used by core/risk.py ─────────

@dataclass
class _OBSnapshot:
    bid_yes: float | None = None
    bid_no: float | None = None
    ask_yes: float | None = None
    ask_no: float | None = None
    spread_yes: float | None = None
    depth_top5_usd_yes: float = 2000.0
    depth_top5_usd_no: float = 2000.0
    imbalance: float = 0.0


@dataclass
class _Signal:
    confidence: float = 0.0
    side: str = "BUY_YES"


@dataclass
class _Market:
    resolved: bool = False
    closed: bool = False
    active: bool = True
    start_iso: str | None = None
    market_type: str = "moneyline"
    yes_token_id: str | None = None
    no_token_id: str | None = None


@dataclass
class _ModeCtx:
    profile_multipliers: dict[str, float] = field(default_factory=dict)


@dataclass
class _Trade:
    id: int | None = None
    entry_px: float | None = None
    qty: float | None = None
    side: str = "BUY_YES"
    market_slug: str = ""
    status: str = "closed"


# ── DB helpers ────────────────────────────────────────────────────────────────

_LOAD_SQL = """
    SELECT id, entry_px, qty, side, market_slug, status,
           confidence, pnl_usd, reason_close
    FROM trades
    WHERE status NOT IN ('open')
    ORDER BY id
"""

_SL_REASONS = ("stop_loss", "gap_stop")


def load_trades(db_path: str) -> list[dict[str, Any]]:
    if not os.path.exists(db_path):
        print(f"[WARN] DB not found: {db_path}", file=sys.stderr)
        return []
    with sqlite3.connect(db_path, timeout=5.0) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(_LOAD_SQL).fetchall()
    return [dict(r) for r in rows]


def _is_sl_close(reason: str | None) -> bool:
    return bool(reason and any(r in reason for r in _SL_REASONS))


# ── Row → replay objects ──────────────────────────────────────────────────────

def row_to_objects(
    row: dict[str, Any],
) -> tuple[_Trade, _Signal, _OBSnapshot, _Market, _ModeCtx]:
    side = row.get("side") or "BUY_YES"
    entry_px = float(row.get("entry_px") or 0.0)

    # Synthetic OB: pass-through for all OB gates.
    # bid capped at 0.899 so near-resolution entry gate never fires spuriously.
    safe_bid = min(entry_px * 0.97, 0.899)
    ob = _OBSnapshot(
        bid_yes=safe_bid if side == "BUY_YES" else None,
        bid_no=safe_bid if side == "BUY_NO" else None,
        ask_yes=entry_px if side == "BUY_YES" else 1.0 - entry_px,
        ask_no=entry_px if side == "BUY_NO" else 1.0 - entry_px,
        spread_yes=0.01,
        depth_top5_usd_yes=2000.0,
        depth_top5_usd_no=2000.0,
        imbalance=0.0,
    )

    sig = _Signal(confidence=float(row.get("confidence") or 0.0), side=side)

    trade = _Trade(
        id=row.get("id"),
        entry_px=entry_px,
        qty=float(row.get("qty") or 0.0),
        side=side,
        market_slug=str(row.get("market_slug") or ""),
        status=str(row.get("status") or "closed"),
    )

    return trade, sig, ob, _Market(), _ModeCtx()


# ── Config patching ───────────────────────────────────────────────────────────

# Always disable live-DB exposure check during replay
_REPLAY_FORCE: dict[str, Any] = {"MAX_TOTAL_COMMITTED_USD": 0.0}


def _save(module: Any, keys: list[str]) -> dict[str, Any]:
    return {k: getattr(module, k) for k in keys if hasattr(module, k)}


def _apply(module: Any, overrides: dict[str, Any]) -> None:
    for k, v in overrides.items():
        if hasattr(module, k):
            orig_type = type(getattr(module, k))
            setattr(module, k, orig_type(v))
        else:
            print(f"[WARN] Unknown risk constant: {k}", file=sys.stderr)


def _restore(module: Any, saved: dict[str, Any]) -> None:
    for k, v in saved.items():
        setattr(module, k, v)


# ── SL cluster analysis ───────────────────────────────────────────────────────

def count_sl_clusters(rows: list[dict[str, Any]], window: int = 3, min_run: int = 3) -> int:
    """Count distinct SL-cluster events (≥min_run consecutive SL trades within window IDs)."""
    sl_ids = [r["id"] for r in rows if _is_sl_close(r.get("reason_close"))]
    if len(sl_ids) < min_run:
        return 0
    clusters, run = 0, 1
    for i in range(1, len(sl_ids)):
        if sl_ids[i] - sl_ids[i - 1] <= window:
            run += 1
            if run == min_run:
                clusters += 1
        else:
            run = 1
    return clusters


def count_blocked_sl_clusters(blocked_sl_ids: list[int], window: int = 3, min_run: int = 3) -> int:
    if len(blocked_sl_ids) < min_run:
        return 0
    ids = sorted(blocked_sl_ids)
    clusters, run = 0, 1
    for i in range(1, len(ids)):
        if ids[i] - ids[i - 1] <= window:
            run += 1
            if run == min_run:
                clusters += 1
        else:
            run = 1
    return clusters


# ── Core evaluation ───────────────────────────────────────────────────────────

def evaluate_config(
    rows: list[dict[str, Any]],
    overrides: dict[str, Any],
    config_name: str,
) -> dict[str, Any]:
    import core.risk as risk

    # Reset stateful SL tracker for a clean replay run
    risk._sl_cluster.clear()
    risk._sl_cooldown_until_loop = 0
    risk._current_loop = 0

    effective = {**_REPLAY_FORCE, **overrides}
    saved = _save(risk, list(effective))
    _apply(risk, effective)

    from core.risk import check_entry_gates  # noqa: PLC0415 — intentional post-patch import

    winners_blocked = 0
    losers_blocked = 0
    winners_passed = 0
    losers_passed = 0
    saved_usd = 0.0     # absolute PnL of blocked losers (positive = saved losses)
    cost_usd = 0.0      # absolute PnL of blocked winners (positive = missed profits)
    block_reasons: dict[str, int] = {}
    blocked_sl_ids: list[int] = []

    for row in rows:
        trade, sig, ob, market, mode_ctx = row_to_objects(row)
        pnl = float(row.get("pnl_usd") or 0.0)

        ok, reasons = check_entry_gates(
            ob=ob,
            sig=sig,
            mode_ctx=mode_ctx,
            open_count=0,
            open_per_market={},
            market_id=trade.market_slug or "unknown",
            time_to_end_seconds=3600,
            market=market,
            market_cooldown=None,
        )

        if not ok:
            key = (reasons[0].split(":")[0] if reasons else "unknown")
            block_reasons[key] = block_reasons.get(key, 0) + 1
            if pnl > 0:
                winners_blocked += 1
                cost_usd += pnl
            elif pnl < 0:
                losers_blocked += 1
                saved_usd += abs(pnl)
                if _is_sl_close(row.get("reason_close")):
                    blocked_sl_ids.append(row.get("id") or 0)
        else:
            if pnl > 0:
                winners_passed += 1
            elif pnl < 0:
                losers_passed += 1

    _restore(risk, saved)

    return {
        "config": config_name,
        "overrides": overrides,
        "total_evaluated": len(rows),
        "winners_blocked": winners_blocked,
        "losers_blocked": losers_blocked,
        "winners_passed": winners_passed,
        "losers_passed": losers_passed,
        "blocked_pnl_saved_usd": round(saved_usd, 2),
        "blocked_pnl_lost_usd": round(cost_usd, 2),
        "estimated_pnl_delta_usd": round(saved_usd - cost_usd, 2),
        "sl_clusters_avoided": count_blocked_sl_clusters(blocked_sl_ids),
        "block_reasons": dict(sorted(block_reasons.items(), key=lambda x: -x[1])),
    }


# ── Report ────────────────────────────────────────────────────────────────────

_SEP = "=" * 66


def _print_result(r: dict[str, Any], label: str) -> None:
    print(f"\n  {label}: {r['config']}")
    if r["overrides"]:
        for k, v in r["overrides"].items():
            print(f"    override  {k} = {v}")
    n = r["total_evaluated"]
    lb, wb = r["losers_blocked"], r["winners_blocked"]
    lp, wp = r["losers_passed"], r["winners_passed"]
    print(f"  Trades evaluated      : {n}  ({lb+wb} blocked, {lp+wp} passed)")
    print(f"  Losers blocked (saved): {lb:4d}   +${r['blocked_pnl_saved_usd']:.2f}")
    print(f"  Winners blocked (cost): {wb:4d}   -${r['blocked_pnl_lost_usd']:.2f}")
    print(f"  Net PnL delta         :        ${r['estimated_pnl_delta_usd']:+.2f}")
    print(f"  SL cluster seqs avd   : {r['sl_clusters_avoided']}")
    if r["block_reasons"]:
        print(f"  Block reason breakdown:")
        for reason, count in r["block_reasons"].items():
            print(f"    {reason:<44s} {count:4d}")


def print_report(
    baseline: dict[str, Any],
    alts: list[dict[str, Any]],
    hist_clusters: int,
) -> None:
    print(_SEP)
    print("REPLAY HARNESS — COUNTERFACTUAL GUARDRAIL EVALUATION")
    print(_SEP)
    _print_result(baseline, "[BASELINE]")
    for alt in alts:
        _print_result(alt, "[ALT CFG] ")
    print(f"\n  Historical SL cluster events (all trades): {hist_clusters}")
    print(f"  NOTE: OB fields are synthetic — gates most accurate for")
    print(f"        MIN_ENTRY_CONFIDENCE, MIN_CONFIDENCE, entry price gates.")
    print(_SEP)


# ── Preset configs ────────────────────────────────────────────────────────────

PRESETS: dict[str, dict[str, Any]] = {
    "tighter_confidence": {
        "MIN_ENTRY_CONFIDENCE": 0.65,
        "MIN_CONFIDENCE": 0.60,
    },
    "strict_confidence": {
        "MIN_ENTRY_CONFIDENCE": 0.70,
        "MIN_CONFIDENCE": 0.65,
    },
    "relax_confidence": {
        "MIN_ENTRY_CONFIDENCE": 0.55,
        "MIN_CONFIDENCE": 0.50,
    },
}


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Replay historical trades against alternative guardrail configs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--db",
        default=os.getenv("DB_PATH", "trades_sports.db"),
        help="Path to trades SQLite DB (default: trades_sports.db)",
    )
    ap.add_argument(
        "--config",
        metavar="JSON",
        help='Inline JSON override, e.g. \'{"MIN_ENTRY_CONFIDENCE": 0.65}\'',
    )
    ap.add_argument(
        "--config-file",
        metavar="PATH",
        help="JSON file: {name, overrides} dict or list of such dicts",
    )
    ap.add_argument(
        "--preset",
        choices=list(PRESETS),
        help="Named preset configuration",
    )
    ap.add_argument(
        "--all-presets",
        action="store_true",
        help="Evaluate all preset configs",
    )
    ap.add_argument(
        "--json-out",
        action="store_true",
        help="Print results as JSON",
    )
    args = ap.parse_args()

    db_path = args.db if os.path.isabs(args.db) else os.path.join(_ROOT, args.db)
    rows = load_trades(db_path)
    if not rows:
        print("[WARN] No historical trades found. Exiting.")
        sys.exit(0)

    hist_clusters = count_sl_clusters(rows)

    alt_configs: list[tuple[str, dict[str, Any]]] = []
    if args.all_presets:
        alt_configs.extend(PRESETS.items())
    if args.preset and not args.all_presets:
        alt_configs.append((args.preset, PRESETS[args.preset]))
    if args.config:
        alt_configs.append(("cli-override", json.loads(args.config)))
    if args.config_file:
        with open(args.config_file) as fh:
            cf = json.load(fh)
        if isinstance(cf, list):
            for entry in cf:
                alt_configs.append((entry.get("name", "unnamed"), entry.get("overrides", entry)))
        else:
            alt_configs.append((cf.get("name", "file-config"), cf.get("overrides", cf)))

    if not alt_configs:
        # Default when no config specified
        alt_configs = [("tighter_confidence (default)", PRESETS["tighter_confidence"])]

    baseline = evaluate_config(rows, {}, "current config")
    alts = [evaluate_config(rows, cfg, name) for name, cfg in alt_configs]

    if args.json_out:
        print(json.dumps({
            "historical_sl_clusters": hist_clusters,
            "baseline": baseline,
            "alternatives": alts,
        }, indent=2))
    else:
        print_report(baseline, alts, hist_clusters)


if __name__ == "__main__":
    main()
