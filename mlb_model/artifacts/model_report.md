# MLB Win Probability Model Report

**Model:** `lgbm`  **Status:** PROMOTED

## Core Metrics (Test Set 2025)

| Metric | Prior-only | Model | Improvement |
|--------|-----------|-------|-------------|
| Log Loss | 0.794346 | 0.465638 | +0.328708 |
| Brier Score | 0.272617 | 0.156212 | +0.116405 |

## Calibration

- Max calibration error: `0.0432`
- Mean calibration error: `0.0145`
- Tradable zone (55-70%) max error: `0.0212`

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
| [0.00, 0.03) | 16279 | 0.5639 | 0.4568 |
| [0.03, 0.05) | 10027 | 0.5697 | 0.4867 |
| [0.05, 0.08) | 13235 | 0.5847 | 0.5439 |
| [0.08, 0.12) | 15330 | 0.5997 | 0.5678 |
| [0.12, 0.20) | 25468 | 0.6591 | 0.6373 |
| [0.20, 1.00) | 106566 | 0.8925 | 0.8773 |
