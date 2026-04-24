# BOT_BRIDGE Operating Principles

## 1. Two-track system
All work must be classified before action:

### Track A — Plumbing / Runtime Truth
Use for:
- config load
- process sanity
- restart verification
- dashboard truth
- gate wiring / enforcement
- runtime/state accuracy

### Track B — Alpha / Strategy
Use for:
- market selection
- model quality
- entry logic
- confidence meaning
- market-specific containment logic
- replay analysis

### Rule
- Do not mix Track A and Track B in the same task unless explicitly justified.
- If Track A is unproven, Track B is deprioritized.

## 2. Startup proof before live trust
Before live behavior is trusted, the system should prove:
- correct working directory
- correct Python executable
- .env actually loaded
- critical gate config values are visible/proven
- only one clean runtime stack is active
- restart happened after the intended changes

Source-only fixes are not enough when runtime proof is missing.

## 3. Live verification before trust
- Source code presence is not enough.
- Board DONE status is not enough.
- Runtime proof is required before calling a live issue fixed.
- If runtime proof is missing, status should be stated as: `fixed in source, not yet runtime-proven`.

## 4. Evidence framework
Every important analysis should separate:
- observed
- proven
- likely
- ruled out
- next step

Do not collapse these into one confidence statement.

## 5. Read-only before speculative patching
- If root cause is not pinned down, open a read-only audit first.
- Do not permit broad speculative fixes.
- Do not patch multiple layers at once just because symptoms are noisy.

## 6. Loss containment before alpha expansion
Prefer blocking obvious bad losses before trying to improve upside.
Priority examples:
- repeated same-slug re-entry
- repeated same-side re-entry after decisive adverse events
- irrational near-resolution entries
- configuration / runtime mistakes

## 7. Replay-first learning
New strategy ideas should be evaluated by:
- how many losers they would block
- how many winners they would block
- expected pnl delta
- effect on repeat-loss clusters
- replay evidence when possible before live trust

## 8. Board cleanliness vs runtime truth
A clean board does not imply a clean runtime.
A task marked DONE still requires runtime proof when the task concerns live behavior.

## 9. Review language discipline
Reviews should state clearly:
- source-only proof vs runtime proof
- what is still unproven
- whether restart is required
- whether browser refresh is required

## 10. Practical default
When uncertain:
1. prove runtime truth first
2. isolate the smallest failing layer
3. fix the smallest local cause
4. verify live behavior before trust
