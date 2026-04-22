# HANDOFF — DASHBOARD_POLISH_001
## Tighten main dashboard execution view and unify open-count ownership

---

## STATUS: ACTIVE

This is polish/tightening only.

Do not redesign the system.
Do not touch model logic.
Do not touch execution logic.
Do not re-open incident work.

---

## Priority 1 — source ownership cleanup

1. Make `kpi-open`, `cmd-open`, and equivalent main open-position counts derive from the same canonical `openPaperPositions` array
2. Remove timing-sensitive split ownership between `renderState()` and `renderUnifiedPositions()` for those counts
3. Keep the source of truth explicit and singular

---

## Priority 2 — main card usability polish

Improve the active position cards so they are easier to manage at a glance, while preserving truthfulness.

Cards should clearly emphasize:
- side
- matchup
- entry price
- current price
- live PnL
- TP
- SL
- source
- real lifecycle status

---

## Priority 3 — background diagnostics containment

Keep shadow/advisory visible only as secondary diagnostics.
Do not let it visually compete with real open positions.
Do not let diagnostics feel like primary exposure.

---

## Priority 4 — empty state

Make the 0-open-positions state clean and intentional:
- no confusing dead space
- no implication that advisory items are active positions
- clear message that there are currently no live paper positions

---

## Acceptance criteria

1. main open-position counts all derive from one canonical source
2. no timing-sensitive mismatch remains for main open-position counts
3. active cards are clearer and easier to scan
4. shadow stays secondary
5. 0-open state is clean
6. no truth regression
