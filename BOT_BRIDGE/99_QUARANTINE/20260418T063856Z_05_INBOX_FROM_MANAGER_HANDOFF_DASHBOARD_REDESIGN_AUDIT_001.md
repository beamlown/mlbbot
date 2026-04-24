# HANDOFF_DASHBOARD_REDESIGN_AUDIT_001

## Status: HOLD_PENDING_EXECUTION_TRUTH

**Do not begin until:** `DASHBOARD_REDESIGN_VERIFY_001` APPROVED (PASS decision).

---

## What this task is

Phase 6 — final phase. **Audit and closure only. Zero code changes.**

You are comparing the implemented redesign against the original spec and producing the exit report.

---

## What to produce

```
C:/Users/johnny/Desktop/BOT_BRIDGE/08_SHARED_CONTEXT/DASHBOARD_REDESIGN_AUDIT_REPORT_001.md
```

---

## Audit structure

### 1. Spec compliance table
Read `DASHBOARD_REDESIGN_SPEC_001.md`. For every item:
```
| Spec item | Required | Implemented | Status |
| 5 tabs with names | YES | YES | PASS |
| LIVE default tab | YES | YES | PASS |
| backed_team on position cards | YES | YES | PASS |
...
```

### 2. File change map
```
| File | Function/Section | Change |
| dashboard.html | buildLivePositionCards() | NEW — replaces old buildUnifiedPositionCards |
| dashboard.html | switchTab() | NEW |
...
```

### 3. Gap report
```
| Gap | Reason | Acceptable |
| advisory data sparse in GAMES tab when shadow has no recs | shadow engine only runs when bot is active | YES |
...
```

### 4. Incident closure statements (required)

Write these three statements explicitly:

> **BUY_NO pricing:** `current_held_price` for BUY_NO positions now consistently reads `bid_no` in both the execution layer (`core/risk.py`, `core/paper_exec.py` — EXECUTION_HELD_SIDE_SEMANTICS_001) and the display layer (LIVE tab, POSITIONS tab). The SEA/TEX incident root cause is closed at both layers.

> **Close pricing truth:** Exit price for BUY_NO closed positions reflects the NO-side bid at close time. The BOS/MIL incident root cause is closed at the display layer.

> **Shadow segregation:** Shadow/advisory model recommendations are confined to the GAMES tab advisory section only. They do not appear in LIVE or POSITIONS tabs and are visually distinct from position truth.

### 5. Overall verdict
One of: `COMPLETE`, `COMPLETE_WITH_GAPS`, `INCOMPLETE`

---

## Deliverable check

- [ ] `DASHBOARD_REDESIGN_AUDIT_REPORT_001.md` written to `08_SHARED_CONTEXT`
- [ ] Spec compliance table covers every item
- [ ] File change map is complete
- [ ] All three incident closure statements present
- [ ] Overall verdict stated
- [ ] Zero production file changes
