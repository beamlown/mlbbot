"""
tools/shadow_summary.py — Print current shadow mode P&L and recommendation stats.

Reads logs/shadow_recommendations.jsonl and summarizes:
  - Total recommendations logged
  - Actionable (BUY_YES/BUY_NO) count
  - NO_TRADE count and top suppression reasons
  - Resolved vs unresolved actionable recs
  - Shadow win rate and P&L (for resolved recs)
  - Breakdown by edge bucket and inning range
  - Model version seen in log
  - Log file age

Usage:
    python -m tools.shadow_summary
    python -m tools.shadow_summary --log logs/shadow_recommendations.jsonl
    python -m tools.shadow_summary --tail 200    # only last N lines
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _load_log(path: Path, tail: int = 0) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if tail > 0:
        lines = lines[-tail:]
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def summarize(log_path: Path, tail: int = 0) -> None:
    entries = _load_log(log_path, tail)
    if not entries:
        print(f"No entries found in {log_path}")
        return

    # Split by event type
    recs = [e for e in entries if "action" in e]
    outcomes = {e["market_id"]: e["yes_resolved"]
                for e in entries if e.get("event_type") == "outcome"}

    actionable = [r for r in recs if r["action"] in ("BUY_YES", "BUY_NO")]
    no_trades = [r for r in recs if r["action"] == "NO_TRADE"]

    # Top NO_TRADE suppression reasons
    suppression: Counter = Counter()
    for r in no_trades:
        reasons = r.get("reasons") or []
        if reasons:
            suppression[reasons[0]] += 1

    # Model versions seen
    versions = Counter(r.get("model_version", "unknown") for r in recs)

    # Latest timestamp
    ts_list = [r.get("ts", "") for r in recs if r.get("ts")]
    latest_ts = max(ts_list) if ts_list else "none"
    earliest_ts = min(ts_list) if ts_list else "none"

    # Shadow P&L from matched recs
    wins = 0
    losses = 0
    pnl = 0.0
    total_edge = 0.0
    matched = 0

    edge_bucket_wins: dict[str, int] = defaultdict(int)
    edge_bucket_total: dict[str, int] = defaultdict(int)

    inning_wins: dict[int, int] = defaultdict(int)
    inning_total: dict[int, int] = defaultdict(int)

    for r in actionable:
        mid = r["market_id"]
        if mid not in outcomes:
            continue
        matched += 1
        yes_won = outcomes[mid]
        action = r["action"]
        edge = r.get("edge_yes" if action == "BUY_YES" else "edge_no", 0.0)
        ask = r.get("ask_yes" if action == "BUY_YES" else "ask_no") or 0.5
        total_edge += edge
        won = (action == "BUY_YES" and yes_won) or (action == "BUY_NO" and not yes_won)

        # Edge bucket
        e_abs = abs(edge)
        if e_abs < 0.03:
            bucket = "<0.03"
        elif e_abs < 0.05:
            bucket = "0.03-0.05"
        elif e_abs < 0.08:
            bucket = "0.05-0.08"
        elif e_abs < 0.12:
            bucket = "0.08-0.12"
        else:
            bucket = ">=0.12"

        edge_bucket_total[bucket] += 1
        inning = int(r.get("inning") or 0)
        inning_total[inning] += 1

        if won:
            wins += 1
            pnl += (1.0 / ask - 1.0)
            edge_bucket_wins[bucket] += 1
            inning_wins[inning] += 1
        else:
            losses += 1
            pnl -= 1.0

    unresolved = len(actionable) - matched

    # ── Print ──────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  MLB Shadow Mode Summary")
    print(f"{'='*60}")
    print(f"  Log file  : {log_path}")
    print(f"  Earliest  : {earliest_ts}")
    print(f"  Latest    : {latest_ts}")
    print(f"  Tail      : {'all' if tail == 0 else f'last {tail} lines'}")
    print(f"\n--- Recommendation Counts ---")
    print(f"  Total entries logged : {len(recs)}")
    print(f"  Actionable (BUY_*)   : {len(actionable)}")
    print(f"  NO_TRADE             : {len(no_trades)}")
    print(f"  Action rate          : {len(actionable)/len(recs)*100:.1f}%" if recs else "  Action rate: n/a")

    if suppression:
        print(f"\n--- Top NO_TRADE Reasons ---")
        for reason, count in suppression.most_common(8):
            print(f"  {count:4d}  {reason}")

    print(f"\n--- Shadow P&L (resolved only) ---")
    print(f"  Resolved : {matched} / {len(actionable)} actionable ({unresolved} pending)")
    if matched > 0:
        win_rate = wins / matched
        avg_edge = total_edge / matched
        print(f"  Wins     : {wins} ({win_rate*100:.1f}%)")
        print(f"  Losses   : {losses}")
        print(f"  P&L      : {pnl:+.4f} units")
        print(f"  Avg edge : {avg_edge:+.4f}")
        print(f"  ROI      : {pnl/matched*100:+.2f}% per rec")
    else:
        print(f"  No resolved recommendations yet.")

    if edge_bucket_total:
        print(f"\n--- Win Rate by Edge Bucket ---")
        print(f"  {'Bucket':<14} {'N':>4} {'Wins':>5} {'Win%':>7}")
        for bucket in ["<0.03", "0.03-0.05", "0.05-0.08", "0.08-0.12", ">=0.12"]:
            n = edge_bucket_total.get(bucket, 0)
            if n == 0:
                continue
            w = edge_bucket_wins.get(bucket, 0)
            print(f"  {bucket:<14} {n:>4} {w:>5} {w/n*100:>6.1f}%")

    if inning_total:
        print(f"\n--- Win Rate by Inning ---")
        print(f"  {'Inning':<8} {'N':>4} {'Wins':>5} {'Win%':>7}")
        for inn in sorted(inning_total.keys()):
            n = inning_total[inn]
            w = inning_wins.get(inn, 0)
            print(f"  {inn:<8} {n:>4} {w:>5} {w/n*100:>6.1f}%")

    if versions:
        print(f"\n--- Model Versions ---")
        for v, c in versions.most_common():
            print(f"  {c:4d}  {v}")

    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Shadow mode P&L summary")
    parser.add_argument(
        "--log",
        default=os.getenv("SHADOW_LOG_PATH", "logs/shadow_recommendations.jsonl"),
        help="Path to shadow JSONL log",
    )
    parser.add_argument(
        "--tail", type=int, default=0,
        help="Only read last N lines (0 = all)",
    )
    args = parser.parse_args()
    summarize(Path(args.log), tail=args.tail)


if __name__ == "__main__":
    main()
