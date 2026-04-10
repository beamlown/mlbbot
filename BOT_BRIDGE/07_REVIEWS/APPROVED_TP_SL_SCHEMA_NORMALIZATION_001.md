# APPROVED_TP_SL_SCHEMA_NORMALIZATION_001

Status: APPROVED

I reviewed the implementation and approve it for manager handoff.

## Why approved
- Scope stayed tight to the expected files:
  - `sports_bot_v2/core/risk.py`
  - `sports_bot_v2/core/paper_exec.py`
- The change is conservative schema normalization, not a threshold or strategy redesign.
- Canonical helpers were added in `core/risk.py` for committed USD, TP/SL, max loss, held token/side metadata, and bundled risk packet generation.
- `check_exit()` now uses canonical TP/SL helpers instead of scattered inline comparisons.
- `open_position()` now logs a canonical `risk` packet from `risk.py`.
- Threshold constants were left unchanged.

## Verification reviewed
- `python -m py_compile` passed for `core/risk.py`, `core/paper_exec.py`, and `core/types.py`
- code-change scope is limited to `core/risk.py` and `core/paper_exec.py`
- spot checks confirmed helper definitions and `get_risk_packet(...)` integration are present

## Implementation commit
- `f58e6cfb4644350a72cde9ab204733bc1b42056c`

## Worker artifacts
- `C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_TP_SL_SCHEMA_NORMALIZATION_001.json`
- `C:\Users\johnny\Desktop\BOT_BRIDGE\07_REVIEWS\REVIEW_TP_SL_SCHEMA_NORMALIZATION_001.md`

## Manager note
This clears the `core/risk.py` lock for the next risk-control task once board rules allow it.
