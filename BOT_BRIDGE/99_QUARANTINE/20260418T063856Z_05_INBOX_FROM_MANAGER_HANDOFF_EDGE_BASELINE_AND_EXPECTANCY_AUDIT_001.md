# HANDOFF: EDGE_BASELINE_AND_EXPECTANCY_AUDIT_001

## What you are doing
Read-only audit of the bot's full trade history. No code changes. You are computing the honest math on 277 closed trades to answer: does this bot have edge?

## Why this exists
The bot has -$91 total PnL on 277 trades. That looks near-breakeven, but a pre-audit orientation found:
- The top 5 trades alone account for +$1,111. Without them, underlying PnL is -$1,202.
- Three of those top 5 are identical duplicate entries (bug, not alpha).
- Two others were ungated entries at 0.01 price that happen to have won huge — not repeatable under current gates.
- Confidence appears to be **inverted**: higher confidence → lower win rate.
- BUY_NO has positive expectancy (+$5.79/trade). BUY_YES is negative (-$2.90/trade).
- No trades have been placed since the clean restart (n=0 for the verified gate era).

The framework is at `C:\Users\johnny\Desktop\BOT_BRIDGE\08_SHARED_CONTEXT\EDGE_PROOF_FRAMEWORK_001.md`. Read it before starting. It defines the exact pass/fail criteria E1-E8 you must evaluate.

## Step 0 is critical — clarify fee accounting

Read `core/paper_exec.py` to determine whether `pnl_usd` in the `trades` table includes or excludes `fees_usd`. The `fees_usd` column has an average of $1.97/trade and a total of $545 across all trades. If `pnl_usd` is gross (excluding fees), then the true net PnL is -$91 - $545 = -$636. This changes every expectancy calculation. Clarify this first.

## The lad-tor cluster (trades 183, 184, 185)
These three trades are IDENTICAL: same market_slug, same confidence (0.3151), same entry_px (0.1206), same pnl (+$236 each). This is a known duplicate-open bug from a prior code era. Together they contribute +$708 to the total PnL. When computing outlier-removed expectancy, **always exclude these three trades** as a cluster, not just the best single trade.

## The ungated entries (trades 310, 316)
Both entered below MIN_ENTRY_PRICE=0.22 (at 0.010 and 0.011) when the gate was not enforcing. Both happened to win large (+$216 and +$187). These are not repeatable under current gates. Exclude them in the "gated universe" analysis.

## Queries to run
Use `sqlite3 trades_sports.db` or Python's sqlite3 module. All work is SELECT-only.

Key table: `trades`
Relevant columns: `id, ts_open, confidence, entry_px, pnl_usd, fees_usd, side, reason_close, market_slug, status`

Filter to `status='closed'` and `pnl_usd IS NOT NULL` for most analysis. Exclude zero-pnl records (manual closes, resets) when computing expectancy.

## What NOT to do
- Do not edit any file
- Do not compute expectancy on `status='open'` trades
- Do not treat the lad-tor duplicate cluster as evidence of alpha
- Do not conclude edge exists until E1-E8 are all evaluated
- Do not open new tasks — just return findings

## What your result must contain
For each of the 14 required work items, report:
- the query used (or key logic)
- the result numbers
- the interpretation in one sentence

Then state E1-E8 pass/fail explicitly, one line each.

Final section: "VERDICT — does this bot have proven edge? YES / NO / INSUFFICIENT DATA"
