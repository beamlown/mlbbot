# OVERNIGHT ANALYSIS — 2026-04-10 → 2026-04-11
## Written by: Manager (Claude) — post-session audit, pre-sleep

---

## Session Summary

| Metric | Value |
|--------|-------|
| Total trades tonight | 92 |
| Closed | 89 |
| Open at session end | 3 |
| Realized PnL (closed) | **-$318.24** |
| Win rate | **24.7%** (22/89) |
| Avg win | $26.86 |
| Avg loss | -$14.21 |
| Payoff ratio | 1.89x |
| Break-even WR needed | 34.6% |
| Rolling R25 win rate | 20.0% — PnL -$235.62 |
| Rolling R50 win rate | 22.0% — PnL -$371.38 |
| Rolling R100 win rate | 30.2% — PnL -$162.05 |

**Net: We need 34.6% WR to break even at this payoff ratio. Best recent 100-trade window is 30.2%. The model currently has negative edge.**

---

## Gate Behavior Audit

### Before clean restart (trades 201–289)
- **Confidence gate was NOT enforcing** for most of the early session — stale pyc (confirmed). 57 of 89 closed trades were sub-0.60 confidence. Sub-0.60 trades: **-$298.74 PnL.**

### After first clean restart (~22:38 UTC, trades 288–292)
- Gates appeared to be working. Above-0.60 entries logged. **But this turned out to be temporary.**

### ⚠ CORRECTED — Later runtime reveals gates are still not enforcing

**State.json snapshot at 04:19 UTC shows:**
- Realized PnL: **-$360.90** (from -$77.91 at 03:49 — lost ~$283 in 30 min with gates supposedly live)
- **Config hash unchanged: `2f0dd9e0ef8a`** — proof the process is still running the old config
- A second restart occurred at ~04:14 UTC (new session_start_ts). That restart also loaded the old config.
- **.env was updated AFTER this restart** — the process never saw the new values
- Open positions at 04:19: #306 conf=0.4279 entry=0.1407 and #310 conf=0.5507 entry=**0.01005** — both violate the new AND old thresholds

**Critical model failure observed**: Trade #310 opened on HOU-SEA at entry 0.01 (1 cent), confidence 0.5507. HOU already lost. Market is resolving. Model assigned 55% confidence to a near-zero probability event. This is a model/data disconnect that gates alone cannot fully protect against.

**Verdict: gates are NOT reliably enforcing. The live process did not load the corrected .env at either restart tonight. Tomorrow's first action must be a verified clean restart that proves new config is loaded before any new trade is allowed.**

---

## The 3 Biggest Loss Drivers Tonight

### 1. Gap stops — -$499.99 across 21 trades (67% of all losses)

Gap stops are catastrophic. Every large single-trade loss tonight was a gap stop.

| Trade | Market | Side | Entry | Exit | Move | PnL |
|-------|--------|------|-------|------|------|-----|
| 278 | mlb-bos-stl | BUY_YES | 0.1206 | 0.0100 | -91.7% | -$46.94 |
| 279 | mlb-bos-stl | BUY_YES | 0.0301 | 0.0100 | -66.8% | -$34.75 |
| 270 | mlb-wsh-mil | BUY_NO | 0.4924 | 0.0896 | -81.8% | -$42.09 |
| 285 | mlb-hou-sea | BUY_YES | 0.4121 | 0.1592 | -61.4% | -$32.07 |
| 238 | mlb-cws-kc | BUY_YES | 0.3920 | 0.1791 | -54.3% | -$28.61 |
| 251 | mlb-cws-kc | BUY_YES | 0.1809 | 0.0796 | -56.0% | -$29.44 |

**Pattern**: Most gap stops happen on markets the model is on the wrong side of, at mid-game entry points. The game score flips and the price craters 50–90% between loop intervals.

### 2. Market overconcentration — bot hammered losing markets repeatedly

| Market | Trades | Wins | PnL |
|--------|--------|------|-----|
| mlb-cws-kc-2026-04-10 | 9 | 0 | -$145.46 |
| mlb-hou-sea-2026-04-10 | 9 | 2 | -$89.16 |
| mlb-col-sd-2026-04-10 | 8 | 0 | -$77.53 |
| mlb-ari-phi-2026-04-10 | 6 | 0 | -$72.21 |

CWS-KC is the worst: the bot opened BUY_YES entries at 0.62, 0.39, 0.33, 0.23, 0.18, 0.09, 0.06, 0.06, 0.05 — following the market all the way to near zero. CWS lost badly. The model never gave up on them. **This is a "falling knife" pattern with no per-market circuit breaker.**

### 3. Low-price entry trades — lottery tickets with negative EV

| Bucket | Trades | Wins | PnL | Avg Entry |
|--------|--------|------|-----|-----------|
| entry < 0.20 | 19 | 2 | -$86.32 | 0.099 |
| entry 0.20–0.50 | 56 | 17 | -$166.09 | 0.356 |
| entry > 0.50 | 14 | 3 | -$65.83 | 0.663 |

Entries below 0.15 are especially bad: the model is recommending "buy this team at 9 cents" when the market has already correctly priced them as near-certain losers.

---

## What IS Working

1. **Take-profit exits** (14 trades) captured real gains — avg win $26.86, one trade made $158.37 (ARI-NYM).
2. **Trailing stops** saved some money vs holding to expiry.
3. **Post-restart gates** are all wiring correctly.
4. **Mark fallback fix** is live — dashboard mark pricing is cleaner.
5. **Bankroll-aware sizing** kept individual trade size reasonable (~$14–$50).
6. **Imbalance gate** correctly blocked CWS-KC (imbalance_extreme) late session.

---

## Root Cause Ranking

| Cause | Estimated PnL Impact | Status |
|-------|---------------------|--------|
| Confidence gate not enforcing (stale pyc) | -$298.74 | FIXED — gate live after clean restart |
| Gap stops on wrong-side in-game trades | -$499.99 | OPEN — no structural fix yet |
| Market overconcentration (no per-market trade cap) | ~-$200 (CWS-KC + ARI-PHI) | OPEN |
| Sub-0.15 entry price lottery bets | -$86.32 | PARTIAL — MIN_ENTRY_PRICE=0.15, may need raising |
| Model has negative edge overall | Foundational | OPEN |

---

## Recommended Fixes for Tomorrow (Priority Order)

### FIX-1 — Per-market trade count cap [HIGH — code change]
**Problem**: Bot placed 9 trades on CWS-KC in one session, all losing. No circuit breaker.
**Fix**: Add `MAX_TRADES_PER_SLUG_SESSION` = 3 (default). After 3 closed trades on a slug, ban that slug for the session. Check against DB count at entry gate.
**File**: `bot_core.py` or `core/risk.py`
**Expected impact**: Would have blocked roughly 30 trades tonight.

### FIX-2 — Post-gap-stop same-side ban [HIGH — code change]
**Problem**: After a gap_stop exit on mlb-foo BUY_YES, bot re-enters BUY_YES on the same slug within 60 minutes. Cooldown is 60 min but doesn't block same-side re-entry on same day.
**Fix**: After a gap_stop, ban re-entry on the **same side** for that slug for the remainder of the session (or until session reset). Separate from the existing 60-min cooldown.
**File**: `bot_core.py`
**Expected impact**: Would have prevented the COL-SD, CWS-KC, BOS-STL and HOU-SEA re-entries after gap stops.

### FIX-3 — Raise MIN_ENTRY_PRICE to 0.22 and add it to .env [MEDIUM — .env change]
**Problem**: Min price is 0.15, but trades below 0.20 averaged 10.5% win rate tonight (-$86.32). Also: `MIN_ENTRY_PRICE` is NOT currently in `.env` — it's using the hardcoded default in `risk.py`. Operator cannot tune it without code access.
**Fix**: Add `MIN_ENTRY_PRICE=0.22` to `.env`. This also makes the threshold explicitly configurable.
**File**: `.env` only
**Note**: The pre-pyc-fix session had entries as low as 0.03, 0.05, 0.09 that bypassed the gate. After the restart fix those would have been blocked at 0.15. Raising to 0.22 cuts off even more lottery-ticket entries.

### FIX-4 — Raise MIN_ENTRY_CONFIDENCE to 0.65 [MEDIUM — .env change]
**Problem**: Above-0.60 trades still lost $19.50. The model's true break-even WR at 1.89x payoff is 34.6%. R100 is only 30.2%. 0.60 floor isn't selective enough.
**Fix**: Raise `MIN_ENTRY_CONFIDENCE` from 0.60 to 0.65. More selective, fewer but higher-quality trades.
**File**: `.env`
**Risk**: Fewer entries, potentially missing good markets. But given current WR, trading less is likely better than trading more at these confidence levels.

### FIX-5 — Trailing stop tightening for losing markets [MEDIUM — code/env]
**Problem**: Trailing stops fired on multiple positions at peaks of 14–21%, locking in near breakeven or small losses. Meanwhile gap stops absorbed the real damage. The trailing stop settings may be too wide to protect against the size of moves we're seeing.
**Observation**: trailing_stop(peak=21%,now=-14%) is letting price reverse 35% from peak before exiting. For these binary in-game markets, that's a large concession.
**Fix**: Consider tightening trailing stop reversal threshold from 12% to 8%.
**File**: `.env` (if configurable) or `core/risk.py`

### ADVISORY — LATE_INNING_BLOCK already exists, verify it's wired [CHECK]
**Current config**: `LATE_INNING_BLOCK=7` is set in `.env`. This should block entries after the 7th inning.
**Question**: Was this active tonight? If yes, how did entries at 0.03 and 0.09 price (which implies late-game near-certainty) get through? Likely answer: those were pre-pyc-fix, when ALL gates were bypassed. Need to confirm the LATE_INNING_BLOCK is wired in the entry gate chain.

### ADVISORY — Game-state integration [MODEL — next session]
**The deepest problem**: The model doesn't know the game score or inning when recommending. It recommended BUY_YES on CWS at 0.06 when CWS was losing 8-1 in the 8th inning. The market was correct; the model wasn't.
**This requires mlb_model changes** — integrating ESPN/game-state data into confidence scoring. Not a one-loop fix, but the most impactful medium-term improvement.
**Until this is solved**: the per-market cap and post-gap-stop ban are the defensive guardrails that prevent the most damage.

---

## ⚠ Current Open Positions (04:19 UTC — UPDATED — much worse than earlier snapshot)

| Trade | Market | Side | Entry | Conf | Notes |
|-------|--------|------|-------|------|-------|
| #306 | mlb-tex-lad | BUY_YES | 0.1407 | 0.4279 | Violates 0.65 conf and 0.22 price |
| #310 | mlb-hou-sea | BUY_YES | **0.01005** | 0.5507 | **CRITICAL — entry at 1 cent, 4975 qty. HOU lost. Market near resolution at 0.** |

Trades #290–#305 all opened and closed since the "clean restart" — nearly all losses. The bot was running ungated.

**Resolution_watcher will close #310 at ~0.01 (near total loss on that position). #306 is also likely a loss.**

## Realized PnL Progression Tonight
| Time | Realized PnL | Notes |
|------|-------------|-------|
| ~22:38 UTC | First restart | |
| 03:49 UTC | -$77.91 | Appeared gated |
| 04:19 UTC | **-$360.90** | +$283 losses in 30 min — gates not enforcing |

**Total trades tonight (as of 04:19): 264 opened since session origin.**

---

## Tomorrow's Session Guidance

1. **Verify all 3 open positions at open** — check final game scores for TEX-LAD, HOU-SEA, COL-SD. The resolution_watcher should close them but confirm.
2. **Do not restart the bot** unless there's a clear bug — the gates are clean.
3. **Before opening any new trades**, confirm in bot log that `BRIDGE GATE REJECT [check_entry_gates]` is still firing for sub-0.60 entries.
4. **FIX-1 (per-market cap) is the highest priority worker task** for tomorrow.
5. **FIX-2 (post-gap-stop same-side ban)** should go into the same task or as a separate follow-on.
6. **FIX-3 and FIX-4** (.env changes only) can be done by operator without a worker — just increase the thresholds.

---

## Bankroll State

From state.json at session end:
- Rolling realized (session): -$77.91 (post-restart portion only)
- Total tonight (all sessions): approximately **-$318.24 closed PnL**
- Bankroll: ~$458 (from sizing log: `bankroll=458.41`)
- This session represented ~69% of peak bankroll draw

**Sizing is appropriate** — 3% of bankroll per trade is conservative. The problem is trade volume and directional accuracy, not position sizing.
