# HANDOFF: NEAR_RESOLUTION_CONFIDENCE_SANITY_AUDIT_001

## What you are doing
Read-only audit of 3 files to understand why the model assigned ~55% confidence to a market trading at 0.01 (near-certain loser).

## Why this exists
Tonight trade #310 opened on HOU-SEA at entry_px=0.01005, confidence=0.5507. A Polymarket contract at 1 cent means the outcome is 99% decided. The model still said "55% confident in BUY_YES." This is either:
- **(A)** The model never sees current market price — it operates on game-state data that was stale or already decided
- **(B)** The model sees price but doesn't penalize extreme values in its confidence output
- **(C)** A near-resolution suppressor exists somewhere but is not wired into the live entry path
- **(D)** Something else

Your job is to determine which and provide evidence.

## Files to read (all read-only)
1. `core/model_bridge.py` — how does the bridge translate model output into a confidence value? Does it pass current market price to the model?
2. `mlb_model/integration/recommendation_api.py` — where is the model's confidence score actually computed? What inputs does it use?
3. `core/risk.py` — is there any near-resolution suppressor or price-extreme check in the entry gate logic?

Also check `.env` for `LATE_INNING_BLOCK=7` — confirm whether this is actually wired in an entry gate that would fire, and whether it would have caught a 0.01-price market.

## What a good answer looks like
- Exact function/line where confidence is set
- Clear yes/no: does the model receive current Polymarket contract price as an input?
- Classification: A, B, C, or D with supporting quotes from the code
- One-paragraph concrete fix recommendation (described only, not implemented)

## Constraints
- Read only the 3 files listed
- Do not edit anything
- Do not open follow-on tasks
- Do not sweep other mlb_model internals beyond recommendation_api.py
