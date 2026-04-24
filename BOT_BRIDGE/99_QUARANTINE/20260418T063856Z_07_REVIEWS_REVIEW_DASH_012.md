# REVIEW_DASH_012

Decision: APPROVED

## What passed

- **Scope**: only `dashboard.html` modified — matches allowed_files exactly. No server files touched.
- **gameStatusChip() rewritten** (lines 666–673): checks `game_status` field first via `.toUpperCase()`. Priority order: FINAL/POST → FINAL; PRE/WARMUP/SCHEDULED → SCHEDULED; PROGRESS/LIVE → LIVE; fallback inning check; default SCHEDULED. ✅
- **Inning text gated on LIVE** (line 689): `const inn = (statusChip === 'LIVE' && r.inning) ? \`i${r.inning}\` : ''` — pre-game inning noise suppressed. ✅
- **live-dot gated on LIVE** (line 690): `const liveIndicator = statusChip === 'LIVE' ? '<span class="live-dot"></span>' : ''` — no green dot for scheduled games. ✅
- **gameCtxPill updated** (line 727): uses `liveIndicator`, `inn`, `statusChip` — pill still renders for all games (just `game` required, not `game || inn`). ✅
- **Rollback**: `dashboard.html` only — revertable.

## What failed

- None.

## Notes

- The ticker row inning at line 898 still uses the old `r.inning ? \` i${r.inning}\` : ''` pattern — that's a different code path (shadow feed ticker, not position cards) and was outside task scope. Not a blocker.

## Next action

Board is idle. No queued tasks. All known display bugs from the April 5 screenshot are resolved.
