# MLB Win Probability Model Report

**Model:** `lgbm`  **Status:** PROMOTED

## Core Metrics (Test Set 2025)

| Metric | Prior-only | Model | Improvement |
|--------|-----------|-------|-------------|
| Log Loss | 0.794346 | 0.465299 | +0.329047 |
| Brier Score | 0.272617 | 0.156099 | +0.116519 |

## Calibration

- Max calibration error: `0.0386`
- Mean calibration error: `0.0184`
- Tradable zone (55-70%) max error: `0.0179`

## Promotion Check

| Check | Pass |
|-------|------|
| beats_prior_log_loss | PASS |
| beats_prior_brier | PASS |
| reliability_acceptable | PASS |
| no_overconfidence_tradable | PASS |

**Final verdict: PROMOTED**

## Edge Bucket Analysis

| Edge Range | N | YES accuracy | NO accuracy |
|-----------|---|-------------|------------|
| [0.00, 0.03) | 17376 | 0.5517 | 0.4664 |
| [0.03, 0.05) | 11500 | 0.5718 | 0.4982 |
| [0.05, 0.08) | 14798 | 0.5796 | 0.5379 |
| [0.08, 0.12) | 12230 | 0.6128 | 0.5597 |
| [0.12, 0.20) | 25828 | 0.6656 | 0.6263 |
| [0.20, 1.00) | 105173 | 0.8967 | 0.8806 |
