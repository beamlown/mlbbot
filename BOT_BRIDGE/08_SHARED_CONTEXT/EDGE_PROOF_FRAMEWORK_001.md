# EDGE_PROOF_FRAMEWORK_001.md
## Manager artifact — Analytical Specialist Mode
## Issued: 2026-04-11

---

## 1. Rules Read
- BOT_BRIDGE_OPERATING_PRINCIPLES.md: read
- MANAGER_RULES.md: read
- WORKER_RULES.md: read
- REVIEW_RULES.md: read

## 2. Mode
SUPERVISOR + ANALYTICAL SPECIALIST MODE
Track B — Alpha / Strategy (all tasks in this chain are Track B)
Precondition: Track A (plumbing / runtime truth) is now verified. Clean restart confirmed 2026-04-11 with config_hash f87077f219dd, gates at correct thresholds, single process, confidence gate live-firing.

---

## 3. Definition of "Prove Edge"

Edge is proven if and only if ALL of the following hold:

| # | Criterion | Threshold |
|---|-----------|-----------|
| E1 | Positive expectancy after fees/slippage | avg_pnl_net > 0 over a qualifying window |
| E2 | Win rate exceeds break-even after fees | actual_win_rate > break_even_win_rate_with_fees |
| E3 | Result not explained by one lucky cluster | removing single best slug still leaves E1+E2 intact |
| E4 | Result not explained by one lucky trade | removing single best trade still leaves E1+E2 intact |
| E5 | Result holds in clean-runtime window | E1+E2 proven separately in post-clean-restart trades only |
| E6 | Confidence is predictive | higher confidence bucket → higher win rate, monotonically over n≥20 buckets |
| E7 | Result holds for the gated universe | E1+E2 proven for trades where conf≥0.65 AND entry_px≥0.22 only |
| E8 | Beats random-side baseline | expectancy > random baseline over same trade universe |

Edge is **NOT** proven if:
- Any single trade accounts for >25% of total positive PnL
- Any single slug accounts for >30% of total positive PnL
- Confidence is non-predictive or inverted
- The clean-runtime window (post-2026-04-11 restart) has insufficient sample (n<30) — defer verdict

---

## 4. What the Data Already Shows (Pre-Audit Orientation)

These are observed facts from a direct DB query run 2026-04-11. They inform task design but are NOT the formal audit.

### A. Break-Even Win Rate

```
avg_win (gross pnl_usd)  = $44.94  (n=71)
avg_loss (gross pnl_usd) = $16.41  (n=200)
avg_fee                  = $1.97   (recorded separately in fees_usd)
```

**Gross break-even win rate** = 16.41 / (44.94 + 16.41) = **26.7%**

**Actual win rate** = 71/271 = **26.2%** (non-zero outcomes only)

**Status:** Below break-even by ~0.5 percentage points.

**Fee accounting confirmed:** pnl_usd is already net of fees (entry_fees + exit_fees deducted in close path in paper_exec.py). The fees_usd column is a separate accounting record only. Break-even win rate is 26.7% net — no further fee adjustment needed.

### B. Single-Trade / Single-Slug Concentration

**Top 5 trades by PnL:**
- id=183, lad-tor, conf=0.315, entry=0.12, pnl=+$236 (take_profit)
- id=184, lad-tor, conf=0.315, entry=0.12, pnl=+$236 (take_profit) — **IDENTICAL to 183**
- id=185, lad-tor, conf=0.315, entry=0.12, pnl=+$236 (take_profit) — **IDENTICAL to 183 and 184**
- id=310, hou-sea, conf=0.55, entry=0.010, pnl=+$216 (take_profit) — entry below MIN_ENTRY_PRICE (ungated)
- id=316, tex-lad, conf=0.39, entry=0.011, pnl=+$187 (take_profit) — entry below MIN_ENTRY_PRICE (ungated)

**Total top-5 contribution: +$1,111**
**Total PnL: -$91**
**PnL excluding top 5: -$1,202**

Trades 183/184/185 are three identical entries on the same market at the same price. This is a known duplicate-open bug (pre-fix). Their +$708 combined PnL is not repeatable alpha.

Trades 310 and 316 entered at 0.01 and 0.011 — below the now-enforced MIN_ENTRY_PRICE floor. These are ungated anomalies that happened to win huge. Also not repeatable under current gates.

**E3 and E4 fail on current data.** The full trade history does not prove edge.

### C. Confidence Predictivity

| Bucket | n | Win% | Avg PnL |
|--------|---|------|---------|
| <0.30 | 14 | 42.9% | +$6.54 |
| 0.30-0.40 | 95 | 34.7% | +$8.74 |
| 0.40-0.50 | 44 | 29.5% | -$1.51 |
| 0.50-0.55 | 11 | 18.2% | -$3.02 |
| 0.55-0.60 | 14 | 14.3% | +$3.88* |
| 0.60-0.65 | 83 | 16.9% | -$9.95 |
| 0.65-0.70 | 3 | 0.0% | -$7.03 |
| >=0.70 | 7 | 14.3% | -$17.16 |

*0.55-0.60 positive avg_pnl is suspicious — likely contains near-resolution winners.

**Confidence is INVERTED.** Higher confidence → lower win rate. This is a critical finding. The model's confidence output is not calibrated as a probability. The 0.30-0.40 bucket outperforms 0.60-0.65. This means the confidence gate at 0.65 is not filtering low-quality signals — it may be filtering the better signals.

**E6 fails on current data.**

### D. Side Asymmetry

| Side | n | Win% | Avg PnL |
|------|---|------|---------|
| BUY_NO | 80 | 32.5% | +$5.79 |
| BUY_YES | 191 | 23.6% | -$2.90 |

BUY_NO has a materially higher win rate and positive expectancy. BUY_YES is deeply negative. This asymmetry is large and persistent — warrants separate treatment in every audit.

### E. Era Analysis

| Era | Trades | Win% | PnL | Notes |
|-----|--------|------|-----|-------|
| id≤200 (early) | 153 | 29.4% | +$240 | Includes lad-tor +$708 duplicates |
| id 201-237 (pre-gate-wire) | 35 | 31.4% | +$86 | |
| id 238-277 (post-gate-wire, broken runtime) | 40 | 25.0% | -$191 | Pyc stale, dual stack, gates not enforcing |
| Post-clean-restart (2026-04-11) | 0 | — | — | No trades yet |

Early era positive PnL is entirely explained by the lad-tor duplicate cluster (+$708). Without it: early era PnL = -$468.

**No era has proven edge on a clean, gate-enforced sample.**

---

## 5. Task Order

| # | Task ID | Type | Depends On | Notes |
|---|---------|------|------------|-------|
| 1 | EDGE_PROOF_FRAMEWORK_001 | Manager artifact | — | This document |
| 2 | EDGE_BASELINE_AND_EXPECTANCY_AUDIT_001 | Read-only audit | Framework | Full historical analysis with fee clarification, segment breakdowns, outlier removal, break-even math |
| 3 | CLEAN_RUNTIME_WINDOW_AUDIT_001 | Read-only audit | Gate verification PASS | Isolate post-2026-04-11 restart trades only. Deferred until n≥30 |
| 4 | MODEL_SIGNAL_QUALITY_AUDIT_001 | Read-only audit | Expectancy audit | Is confidence actually predictive? Calibration curve. shadow_recommendations analysis |
| 5 | Code / model task | TBD | Audits 2+3+4 | Only open if evidence justifies specific smallest fix |

**No code tasks open until audits 2, 3, 4 are complete and reviewed.**

---

## 6. Pass / Fail Criteria (Explicit)

### To declare "this bot has edge":
ALL must pass:
- [ ] E1: avg_pnl_net > $0 over n≥50 in a qualifying window
- [ ] E2: win_rate > break_even_win_rate (with fees) over n≥50
- [ ] E3: removing the single best slug, E1+E2 still hold
- [ ] E4: removing the single best trade, E1+E2 still hold
- [ ] E5: E1+E2 proven in post-2026-04-11 restart window (n≥30 required)
- [ ] E6: confidence monotonically predictive over n≥20 buckets
- [ ] E7: E1+E2 proven for conf≥0.65 + entry_px≥0.22 universe
- [ ] E8: expectancy > random-side baseline

### To declare "this bot does NOT have edge":
ANY of:
- E1 fails: avg_pnl_net ≤ 0 after outlier removal
- E2 fails: win rate ≤ break_even after fees, robust to outlier removal
- E3 fails: single slug explains all positive PnL
- E4 fails: single trade explains all positive PnL
- E6 fails: confidence is non-predictive or inverted over n≥20 buckets
- E7 fails: gated universe has no positive expectancy

### Current Status (pre-audit):
| Criterion | Status |
|-----------|--------|
| E1 (positive expectancy after fees) | FAIL — -$91 net (fees already included in pnl_usd) |
| E2 (win rate > BE with fees) | MARGINAL FAIL — 26.2% actual vs 26.7% break-even (net) |
| E3 (not single-slug concentrated) | FAIL — lad-tor explains all positive PnL |
| E4 (not single-trade concentrated) | FAIL — top 5 trades = +$1,111 vs total -$91 |
| E5 (clean runtime window) | DEFERRED — n=0 post-clean-restart |
| E6 (confidence predictive) | FAIL — inverted confidence-outcome relationship |
| E7 (gated universe edge) | DEFERRED — insufficient gated-era data |
| E8 (beats random baseline) | UNKNOWN — requires audit |

**Current verdict: NO PROVEN EDGE.** This is not a negative judgment on the strategy's future potential — it is an honest statement of what the current evidence supports.

---

## 7. What the Audits Must Resolve

### EDGE_BASELINE_AND_EXPECTANCY_AUDIT_001 must answer:
1. Does pnl_usd include or exclude fees_usd? (compute both gross and net)
2. What is net break-even win rate?
3. What is net expectancy overall, last 25/50/100, by era?
4. What is expectancy with top-5 outliers removed?
5. BUY_NO vs BUY_YES expectancy separately
6. Entry price bucket analysis: which buckets survive gate (≥0.22)?
7. Confidence bucket analysis: is there ANY bucket with positive net expectancy?
8. Per-slug analysis: which slugs are profitable at >5 trades?
9. Random-side baseline: what would expectancy be if side was random?

### CLEAN_RUNTIME_WINDOW_AUDIT_001 (deferred, n≥30 required):
1. Every trade opened post-2026-04-11 restart
2. Does this window satisfy E1-E4?
3. Are gates blocking the right signals?

### MODEL_SIGNAL_QUALITY_AUDIT_001 must answer:
1. Is confidence from recommendation_api.py calibrated as a probability?
2. What does the confidence distribution look like in shadow_recommendations.jsonl?
3. Is there a calibration curve (confidence vs realized outcome)?
4. Does the near-resolution inflation explain the inverted confidence curve?

---

## 8. Immediate Implications (No Code Change Required)

These are observations, not tasks:

1. **Confidence gate at 0.65 may be filtering better signals.** The 0.30-0.40 bucket outperforms 0.60-0.70 materially. Before assuming the gate is protecting, audit whether it's actually selecting better signals.

2. **BUY_NO has positive historical expectancy (+$5.79/trade).** BUY_YES is deeply negative (-$2.90/trade). Whether this is structural or sample noise is a key audit question.

3. **The 0.10-0.15 entry price bucket has high avg PnL (+$20.97) but will now be blocked by MIN_ENTRY_PRICE=0.22.** This bucket contains 25 trades with 24% win rate and +$524 total PnL. Partially driven by near-resolution outliers, but worth examining whether the MIN_ENTRY_PRICE=0.22 floor is correctly set or too conservative.

4. **Post-clean-restart n=0.** We cannot say anything about whether the strategy works under clean conditions. We need live data from the gated universe.
