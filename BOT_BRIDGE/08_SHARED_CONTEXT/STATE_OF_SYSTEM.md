# STATE_OF_SYSTEM

## Current architecture
- `mlb_model` = upstream recommendation/shadow logic.
- `sports_bot_v2` = downstream paper execution, lifecycle, DB truth, dashboard/API serving.
- User-facing live position truth must come from real paper trades only.
- Shadow remains diagnostics/background only.

## Current process topology
- Duplicate-entry / topology incident has been contained.
- Canonical launcher-managed stack was restored and final alignment check succeeded.
- Final verified state after addendum: DB open rows, `/api/trades`, and `/api/state` aligned at 0 open.

## Current bridge status
- Bridge is operational and no longer in duplicated-writer incident state.
- Unique open-slug DB protection index was created in live DB after remediation.
- Existing duplicate open rows were remediated under approved void rule before index creation.

## Current dashboard status
### Production dashboard (`dashboard.html`)
- Main positions truth comes from real open paper trades only.
- Shadow stays diagnostics only.
- Main open-position counts were stabilized to a canonical source.
- Accounting fields (available cash / capital committed / live equity context) were improved.
- Baseball-monitor feel was partially restored into the main active card.
- Trade log was demoted structurally from default emotional ownership.

### Dashboard V2 (`dashboard_v2.html`)
- Fresh side-by-side shell exists.
- Built from scratch; production dashboard not replaced.
- Uses current endpoints:
  - `/api/state`
  - `/api/trades`
  - `/api/games`
  - `/api/mlb-shadow`
- Designed as game-first and position-first with secondary trade/shadow areas.
- Awaiting verification/polish, not production promotion.

## Current known bugs / gaps
- Production dashboard still may not fully satisfy the desired baseball-monitor feel even after restore attempts.
- `dashboard_v2.html` exists but still needs explicit verification against live endpoint behavior before being considered usable.
- Some final premium/polish-level UX work is still better suited for Claude later.

## Current resolved incidents
- Duplicate-entry live incident: contained.
- Duplicate launcher/process topology: contained and cleaned.
- Live DB path/index ambiguity: resolved enough to prove missing index and remediate.
- DB duplicate open rows: remediated.
- Final state alignment incident: resolved enough for return to dashboard work.

## Current open questions
- Is `dashboard_v2.html` already good enough to use as a serious staging replacement after verification?
- How much of the remaining baseball-monitor feel should be completed by GPT vs left for Claude premium polish?

## Current production-safe truths that must not regress
- Main live positions must come from real paper trades only.
- No shadow-only positions in main live area.
- Shadow remains diagnostics/background only.
- One canonical source for main open-position counts.
- Accounting must remain truthful:
  - available cash reflects committed capital
  - committed capital should not zero out while a trade is open
  - live equity and unrealized must remain internally consistent
- No reintroduction of duplicate writer topology or duplicate open-row behavior.

## If Claude returned right now
Claude should assume:
- incident state is no longer the main blocker
- system truth has been stabilized enough to focus on dashboard/V2 refinement
- V2 shell exists and should be evaluated before any premium redesign work starts
