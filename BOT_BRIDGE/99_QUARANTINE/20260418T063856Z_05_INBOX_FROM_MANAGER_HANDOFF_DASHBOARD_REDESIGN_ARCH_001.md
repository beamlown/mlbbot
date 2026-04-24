# HANDOFF_DASHBOARD_REDESIGN_ARCH_001

## Status: HOLD_PENDING_EXECUTION_TRUTH

**Do not begin until:** `EXECUTION_HELD_SIDE_SEMANTICS_001` is APPROVED and `REVIEW_EXECUTION_HELD_SIDE_SEMANTICS_001.md` exists in `07_REVIEWS`.

---

## What this task is

Phase 0 of the dashboard redesign pack. **Spec/architecture only — zero code changes.**

Your job is to read the current dashboard.html and dashboard_server.py, understand the full payload contract, then write a written architecture specification to:

```
C:/Users/johnny/Desktop/BOT_BRIDGE/08_SHARED_CONTEXT/DASHBOARD_REDESIGN_SPEC_001.md
```

Every subsequent redesign phase will follow this spec. If you write a bad spec, every downstream phase will be wrong.

---

## What the spec must cover

1. **5-tab layout:** LIVE (default), POSITIONS, GAMES, HISTORY, SYSTEM — tab names, default, purpose of each
2. **LIVE tab focal area order:** game monitor → position cards → account strip
3. **Payload mapping table:** for each frontend field, the exact API source (`/api/state`, `/api/games`, `/api/trades`, SSE stream)
4. **Frontend/backend split:** what is computed client-side vs returned by server
5. **Demotion list:** what currently dominates the page that must be moved to secondary tabs
6. **New server fields required (if any):** must be minimal and justified
7. **Truth-model preservation checklist:** explicit pass/fail for each constraint:
   - `current_held_price` = stream-backed held-side bid only
   - `bid_no` used for BUY_NO positions (not `bid_yes`)
   - shadow advisory excluded from LIVE and POSITIONS tabs
   - no new price writers introduced
   - backed_team / faded_team semantics used for display

---

## Key truth model facts to preserve

- **BUY_YES positions:** `current_held_price = bid_yes`
- **BUY_NO positions:** `current_held_price = bid_no` ← this was the SEA/TEX incident root cause
- **Unrealized PnL:** `(current_held_price - entry_px) * qty` — works identically for both sides
- **Close pricing:** exit_px = bid of held side at close ← this was the BOS/MIL incident root cause
- **Price authority chain:** polymarket stream → state_hub → SSE `/api/stream/state` → frontend
- **Shadow advisory:** GAMES tab only, clearly labeled, never competing with position truth

---

## Output

Single file: `DASHBOARD_REDESIGN_SPEC_001.md` in `08_SHARED_CONTEXT`.

No other files created or modified.

---

## Deliverable check

- [ ] `DASHBOARD_REDESIGN_SPEC_001.md` exists
- [ ] Spec defines all 5 tabs with names and default
- [ ] Spec includes payload mapping table
- [ ] Spec includes truth-model preservation checklist
- [ ] Zero production file changes
