# REVIEW_EDGE_BASELINE_AND_EXPECTANCY_AUDIT_001.md

## Verdict
APPROVED

## Decision
Approve `EDGE_BASELINE_AND_EXPECTANCY_AUDIT_001`. Move to DONE. Activate `MODEL_SIGNAL_QUALITY_AUDIT_001` as next. Defer `CLEAN_RUNTIME_WINDOW_AUDIT_001` until post-restart n≥30.

## What was confirmed

- Fee accounting clarified correctly from source: `pnl_usd` is already net of fees. The preliminary -$636 estimate in the framework was wrong and is now corrected.
- All 14 required work items addressed.
- E1–E8 verdicts stated explicitly with evidence.
- Outlier removal computed correctly (top 5 trades, lad-tor slug).
- Confidence bucket table produced.
- Side asymmetry reported.
- Gated-universe slice correctly identified as n=5 (insufficient).
- No files modified.

## E1–E8 Verdict Summary

| Criterion | Verdict | Key number |
|-----------|---------|------------|
| E1 — positive net expectancy | **FAIL** | -$91.13 net, avg -$0.33/trade |
| E2 — win rate > break-even | **MARGINAL FAIL** | 26.2% actual vs 26.7% required |
| E3 — not single-slug concentrated | **FAIL** | lad-tor = +$630.79, explains all positive offset |
| E4 — not single-trade concentrated | **FAIL** | top 5 = +$1,111 vs -$91 total; ex-top-5 = -$1,202 |
| E5 — clean-runtime window | **DEFERRED** | n=0 post-restart |
| E6 — confidence predictive | **FAIL** | 0.30-0.40 best (+$830, 34.7% WR); 0.60-0.65 worst (-$826, 16.9% WR) |
| E7 — gated universe edge | **DEFERRED** | n=5, -$59.77 |
| E8 — beats random-side baseline | **UNRESOLVED** | proxy +$1.40, needs proper audit |

**Current verdict: NO PROVEN EDGE.**

## What this result changes

1. **Fee scare is resolved.** The -$91 figure is real net PnL. The strategy is not buried under hidden fees.

2. **The real problem is concentration and signal inversion.** Removing the lad-tor cluster (probable duplicate-open bug) and the two ungated near-resolution winners leaves approximately -$1,202 on 272 trades. That is not recoverable by a gate adjustment.

3. **Confidence inversion is the critical finding.** The current gating strategy (min 0.65) is selecting from the worst-performing confidence bucket in the historical sample. The 0.30-0.40 bucket outperforms the 0.60-0.65 bucket by over $1,600 in aggregate. This means either: (a) the confidence formula is uncalibrated and not measuring what we think it is, (b) the 0.30-0.40 wins are driven by the same lad-tor outlier cluster, or (c) something structural about lower-confidence recs is different. MODEL_SIGNAL_QUALITY_AUDIT_001 must answer this.

4. **BUY_NO asymmetry is real but requires caution.** +$464 vs -$555 is a large gap. Whether structural or driven by a few slugs needs investigation before acting on it.

5. **E5 and E7 remain the most important open questions.** The clean-restart era (conf≥0.65, entry≥0.22) is the only universe we care about going forward. It has n=5 in historical data. We cannot make decisions from that. Accumulate post-restart trades.

## One accounting note

E8 (random-side baseline) was evaluated with a proxy, not a full simulation. The reported +$1.40 average on a random-side baseline is directionally useful but not rigorous. The formal baseline needs to flip the actual side on each trade and compute counterfactual PnL. This is low priority — E1-E4 and E6 already tell the story — but should be completed in the full MODEL_SIGNAL_QUALITY_AUDIT_001.

## Next task

**`MODEL_SIGNAL_QUALITY_AUDIT_001`** — activate immediately.

Primary questions:
1. Is the 0.30-0.40 confidence bucket performance driven entirely by the lad-tor duplicate cluster? If yes, confidence inversion disappears after outlier removal.
2. What does the confidence distribution look like in the shadow recommendations log?
3. Is there any sub-segment (BUY_NO only, clean era only, post-gate era only) where confidence is actually predictive?
4. What drives the BUY_NO vs BUY_YES asymmetry at the signal level?

## Manager judgment

Close `EDGE_BASELINE_AND_EXPECTANCY_AUDIT_001` to DONE.
Dispatch `MODEL_SIGNAL_QUALITY_AUDIT_001`.
Defer `CLEAN_RUNTIME_WINDOW_AUDIT_001` — revisit when post-restart n≥30.
Do not open any code or model-fix tasks until MODEL_SIGNAL_QUALITY_AUDIT_001 completes.
