# PROVISIONAL_REVIEW_BRIDGE_CONTRACT_001

Decision: PROVISIONALLY_APPROVED

## What changed

The bridge contract is now explicitly richer.

Before this task, `core/model_bridge.py` collapsed mlb_model recommendations down to a very thin execution payload:
- slug
- market_id
- side
- entry_px
- confidence
- edge
- source

After this task, the bridge preserves a substantially larger model-intent payload, including:
- market identity
- team/matchup semantics
- held outcome label
- model probabilities
- both-side market costs / ask prices
- both edge fields plus chosen edge
- confidence
- size tier / size multiplier
- optional recommended size / TP / SL fields if present
- reasons
- game-state context
- freshness timestamps / age data

## Why this is the right scope

- No new strategy logic was added.
- No local signal generation was re-opened.
- No execution redesign was attempted.
- This is a transport/preservation improvement only.

## Verification basis

- Live mlb_model recommendation log still shows the richer emitted recommendation fields.
- `core/model_bridge.py` now preserves those fields in the approved intent payload instead of thinning them away.
- No `bot_core.py` change was required for this first contract-expansion step.

## Remaining follow-up

A later task can teach execution/runtime/dashboard layers to consume more of the preserved fields directly, but the contract-preservation step itself is now in place.
