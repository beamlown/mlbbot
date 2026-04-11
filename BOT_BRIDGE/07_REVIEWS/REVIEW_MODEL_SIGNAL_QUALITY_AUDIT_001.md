# REVIEW_MODEL_SIGNAL_QUALITY_AUDIT_001.md

## Verdict
APPROVED

## Decision
Approve `MODEL_SIGNAL_QUALITY_AUDIT_001`. Move to DONE. Confirm `CLEAN_RUNTIME_WINDOW_AUDIT_001` as next — remains deferred until post-restart n≥30. Do not open any code or model-fix tasks.

## What was confirmed

- Central outlier hypothesis tested correctly: removing trades 183/184/185/316 flips the 0.30-0.40 bucket from +$830 to -$65.
- BUY_NO advantage at low confidence traced to lad-tor cluster within that bucket (+$836 / 31 trades for BUY_NO vs -$6 for BUY_YES in the same bucket).
- Slug concentration within the 0.30-0.40 bucket confirmed: lad-tor alone = +$687, tex-lad adds +$134.
- High-confidence bucket weakness is independently confirmed and not explained by the outlier removal.
- Failure mechanism for 0.60-0.65 bucket identified: stop_loss (-$587) + gap_stop (-$683) damage, not insufficient winners. Take_profit in that bucket is +$446, which would be positive on its own.
- No files modified.

## Finding Summary

| Question | Finding |
|----------|---------|
| S1 — does inversion survive outlier removal? | **NO** — 0.30-0.40 flips from +$830 to -$65 after removing 4 outliers |
| S2 — is BUY_NO advantage structural? | **OUTLIER_DRIVEN** at low confidence — advantage concentrated in lad-tor cluster |
| S3/S4 — shadow confidence distribution | Not completed (shadow log accessed but outcome matching blocked by zero outcome events) |
| S5 — shadow BUY_YES/BUY_NO ratio | Not completed (no outcome data to separate signal from noise) |
| S6 — BUY_NO asymmetry by entry price / close reason | Reason_close analysis completed: BUY_NO advantage within 0.30-0.40 is entirely take_profit driven; BUY_YES in 0.60-0.65 is stop_loss/gap_stop dominated |
| S7 — confidence formula saturation | Identified from formula: edge_score saturates at 1.0 when edge ≥ 0.15; data_quality and spread_quality dominate at high confidence |
| S8 — shadow-to-DB calibration curve | Not completed — zero outcome events in shadow log prevents calibration |
| S9 — E8 proper random-side baseline | Not completed — deferred to a future focused audit |

**confidence_inversion_verdict: NO** — largely artifact
**buy_no_advantage_verdict: OUTLIER_DRIVEN** at current evidence level
**e8_verdict: INSUFFICIENT_DATA**

## What this result changes

1. **The confidence inversion alarm is resolved.** The gate at ≥0.65 is not selecting demonstrably worse signals based on the historical record. The 0.30-0.40 bucket was inflated by 4 trades that will never recur under current gates. The gate is defensible.

2. **A new, cleaner problem is identified: exit damage on high-confidence trades.** The 0.60-0.65 bucket's -$826 is not a win-rate problem. Take_profit in that bucket is +$446. Stop_loss and gap_stop together are -$1,270. This means the model is finding correct-direction trades in some cases, but entries are getting stopped out before resolution. The two candidate explanations are: (a) pre-fix era contamination — many of these trades were opened during the broken-runtime era where the gate wasn't enforcing, entries were worse quality, and the bot was running with stale pyc; (b) exit parameters too tight for the characteristic volatility of higher-confidence market conditions. CLEAN_RUNTIME_WINDOW_AUDIT_001 will distinguish these.

3. **BUY_NO vs BUY_YES asymmetry is not yet actionable.** The raw +$5.79 vs -$2.90 gap was driven by the lad-tor cluster. That doesn't mean no asymmetry exists — it means we don't have clean evidence for it yet. Do not adjust side selection based on the historical sample.

4. **E6 is still FAIL, but with a revised interpretation.** The old interpretation was "confidence is anti-predictive." The new interpretation is "confidence is not predictive in the historical contaminated sample, and high-confidence failures are exit-damage dominated, not direction-dominated." This is a materially different diagnostic — it points toward exit behavior investigation, not signal direction investigation.

5. **Shadow log is not yet usable for calibration.** Zero outcome events have been logged — the resolution watcher is not writing to shadow_recommendations.jsonl. This limits future calibration curve work unless outcome logging is activated. Low priority for now — enough data from the DB.

## Unresolved from this audit (carry forward)

- **S8/S9 incomplete:** Calibration curve and E8 proper baseline not computed. E8 remains UNRESOLVED. These are low priority — E1-E4 and E6 already tell the story.
- **Shadow outcome logging gap:** The shadow logger has `log_outcome()` but it is not being called by the resolution watcher. No action required now; note for future calibration work.

## Updated E1-E8 Status

| Criterion | Verdict | Updated interpretation |
|-----------|---------|----------------------|
| E1 — positive net expectancy | **FAIL** | -$91.13 net — unchanged |
| E2 — win rate > break-even | **MARGINAL FAIL** | 26.2% vs 26.7% — unchanged |
| E3 — not single-slug concentrated | **FAIL** | lad-tor +$630 — unchanged |
| E4 — not single-trade concentrated | **FAIL** | top-5 +$1,111 — unchanged |
| E5 — clean-runtime window | **DEFERRED** | n=0 post-restart — unchanged |
| E6 — confidence predictive | **FAIL** (revised) | Inversion is artifact; high-confidence failure is exit-damage, not direction inversion |
| E7 — gated universe edge | **DEFERRED** | n=5 — unchanged |
| E8 — beats random baseline | **UNRESOLVED** | Proper simulation still not run |

**Current verdict: NO PROVEN EDGE.** Unchanged — no new evidence of edge, but the picture is cleaner.

## Manager judgment

Close `MODEL_SIGNAL_QUALITY_AUDIT_001` to DONE.
`CLEAN_RUNTIME_WINDOW_AUDIT_001` remains the next and only pending audit — activate when post-restart n≥30.
Do not open any code, model, or gate-change tasks.
Record the exit-damage pattern in EDGE_PROOF_FRAMEWORK_001 — done.
