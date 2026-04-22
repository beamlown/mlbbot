# REVIEW_DASHBOARD_REDESIGN_ARCH_001

Decision: APPROVED

## What passed

- **Scope**: zero production code changes — `dashboard.html` and `dashboard_server.py` untouched. ✅
- **5-tab contract**: LIVE (default), POSITIONS, GAMES, HISTORY, SYSTEM — exact names, correct default. ✅
- **LIVE focal order**: game monitor → position cards → account strip — explicitly specified top-to-bottom. ✅
- **Payload mapping table**: covers `/api/state`, `/api/trades`, `/api/games`, `/api/markets`, `/api/candidates`, `/api/mlb-shadow`, `/api/debug/market-stream`, SSE `/api/stream/state`. All frontend fields mapped to exact source fields. ✅
- **`current_held_price` authority locked**: SSE stream-backed held-side bid only. BUY_YES=`bid_yes`, BUY_NO=`bid_no` stated explicitly. ✅
- **Demotion list**: shadow, trade log, candidates, manual entry, guard stack all demoted with assigned destinations. ✅
- **Truth-model preservation checklist**: 5 constraints listed, all PASS. ✅
- **Shadow policy**: explicitly forbidden from LIVE and POSITIONS as competing truth; confined to GAMES as clearly-labeled advisory only. ✅
- **Frontend/backend split**: server computes price marks, unrealized, equity, TP/SL; client handles presentation only. ✅
- **No new price writers**: stated explicitly — single chain `polymarket stream → state_hub → SSE → frontend`. ✅

## Spec quality notes

- Per-tab `must not show` rules are strong guardrails for reviewer use in later phases.
- Required backend additions section correctly flags `backed_team`, `faded_team`, `held_contract_side` as potentially absent — implementation phases must verify presence before adding.
- Shadow Advisory label `Shadow Advisory — Not Executed` specified exactly for GAMES tab.
- Explicit truth statements at lines 287-292 will be referenced in the VERIFY phase as ground truth.

## What failed

None.

## Next action

- DASHBOARD_REDESIGN_ARCH_001 → DONE
- DASHBOARD_REDESIGN_SHELL_001 → ACTIVE (may begin immediately)
- Spec contract at `08_SHARED_CONTEXT/DASHBOARD_REDESIGN_SPEC_001.md` is the binding reference for all subsequent phases
