# REVIEW_DASH_009

Decision: APPROVED

## What passed

- **Scope**: only `dashboard.html` modified — matches allowed_files exactly. No server files touched.
- **Fix 1 — PnL fallback**: `const unrlzdUsd = r.unrealized_pnl_dollars ?? r.pnl_usd ?? null;` at line 711. Correct — resolved paper trades now show actual DB `pnl_usd` value.
- **Fix 2 — Current price fallback**: `const currentPx = r.current_price ?? (r.resolved ? r.exit_px : null);` at line 722, used in stat box at line 746. Correct — resolved trades show `exit_px` from DB.
- **Fix 3 — Slug parser**: `slugToGameParts()` added at line 472, exact spec match (`/^mlb-([a-z]+)-([a-z]+)-\d{4}-\d{2}-\d{2}$/`, uppercase output). Applied in `buildUnifiedPositionCards()` at lines 680-683 with correct fallback chain. Team display at line 728 updated to `r.tracked_team || game || shortTeam(r.market_slug || '?')`. This also restores the `game` variable used by `gameCtxPill`.
- **Rollback**: `dashboard.html` only — revertable.
- **Sequencing**: Worker correctly held DASH_010 at QUEUED status.

## What failed

- None. No verification output included in result, but all three code changes match the handoff spec exactly and are verifiable by inspection.

## Notes

- The `game` variable at line 683 now uses `_awayTeam`/`_homeTeam` (parsed or shadow-enriched) rather than `r.away_team`/`r.home_team` directly. This means `gameCtxPill` also benefits from slug parsing — a correct side effect.
- No regression risk to open/shadow cards — fallbacks are `??` chains that only activate when shadow fields are absent.

## Next action

Promote DASH_010 to ACTIVE.
