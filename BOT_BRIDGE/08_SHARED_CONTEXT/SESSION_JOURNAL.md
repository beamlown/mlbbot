# SESSION_JOURNAL

## 2026-04-05 13:00–21:20 CDT

### VERIFY_DUPLICATE_ENTRY_001
- Attempted: verification-only check of whether duplicate-entry fix worked in live behavior.
- Changed: BOT_BRIDGE verification/result/review files only.
- Result: blocked; duplicate live process topology and duplicate bridge opens still present.
- Evidence: repeated `BRIDGE SKIP - at capacity (4/3)`, paired duplicate opens, multiple launcher/bot_core/dashboard/resolution_watcher processes.
- Next step: incident process/DB containment.

### INCIDENT_PROCESS_DB_001
- Attempted: process-topology + DB-enforcement incident debug/containment.
- Changed: BOT_BRIDGE task/handoff/result/review files only; contained duplicate launcher tree operationally.
- Result: duplicate process topology proven real; duplicate child launcher tree terminated; live stack reduced.
- Evidence: duplicate process trees, duplicate trade ids 111/112 same slug/price, process snapshot, log evidence.
- Next step: verify live DB path and schema/index state directly.

### INCIDENT_DB_VERIFY_001
- Attempted: verify live DB path, index state, duplicate open rows, and post-containment duplicate behavior.
- Changed: BOT_BRIDGE task/handoff/result/review plus visible read-only helper script.
- Result: exact DB path proven; unique open-slug index missing; duplicate open rows still existed; post-containment no new duplicate pair observed in limited window.
- Evidence: helper script inspection of `trades_sports.db`, duplicate open ids 101/102, absent `idx_trades_one_open_per_slug`.
- Next step: narrow DB remediation.

### INCIDENT_DB_REMEDIATION_001
- Attempted: pause writer, backup DB, remediate duplicate open rows, create unique index.
- Changed: live DB data only under approved cleanup rule; BOT_BRIDGE task/handoff/result/review; backup file and visible remediation script.
- Result: duplicate open rows remediated, index created, DB protected.
- Evidence: backup at `09_ARCHIVE\\trades_sports_pre_remediation_20260405_191246.db`, duplicate row 102 voided, index present after remediation.
- Next step: state/process resync.

### INCIDENT_STATE_RESYNC_001
- Attempted: restore canonical topology and make runtime/API state converge.
- Changed: operational process management only; BOT_BRIDGE task/handoff/result/review.
- Result: partial success first, then blocked due to duplicated non-writer services after restart.
- Evidence: DB and /api/state converged, but duplicate recommendation_api/dashboard/resolution_watcher trees remained.
- Next step: final topology cleanup under explicit ops decision.

### INCIDENT_TOPOLOGY_FINAL_001 + ADDENDUM
- Attempted: stop explicit non-canonical orphan trio and re-verify truth alignment.
- Changed: operational process cleanup only; BOT_BRIDGE result/review/addendum.
- Result: topology cleaned to one canonical launcher tree; final refresh-interval addendum confirmed DB, /api/state, and /api/trades all aligned at 0 open.
- Evidence: single service counts, no new duplicate opens, final addendum with all three sources aligned.
- Next step: move back to dashboard truth work.

### DASHBOARD_TRUTH_002 + VERIFY_DASHBOARD_TRUTH_002
- Attempted: unify dashboard around real paper-trade truth and verify live behavior.
- Changed: `dashboard.html` only.
- Result: main cards built from canonical open paper positions from `/api/trades`; shadow-only entries excluded from main area; live PnL uses real executed basis.
- Evidence: code path `buildOpenPaperPositions(...)`, live verification showing no hard truth regression.
- Next step: polish source ownership and usability.

### DASHBOARD_POLISH_001
- Attempted: tighten count ownership and improve main-card readability.
- Changed: `dashboard.html` only.
- Result: `kpi-open`, `cmd-open`, and `pos-count` all derive from canonical open paper positions; cards/empty state improved.
- Evidence: render path changes, no backend changes needed.
- Next step: broader style/UX polish.

### DASHBOARD_STYLE_FUN_001
- Attempted: style/UX polish without truth-layer changes.
- Changed: `dashboard.html` only.
- Result: stronger command-center feel, better card hierarchy, improved mobile readability, quieter diagnostics.
- Evidence: CSS/layout improvements only.
- Next step: real hierarchy correction and baseball-monitor restore.

### DASHBOARD_HIERARCHY_FIX_001
- Attempted: real structural hierarchy fix so trade log no longer owns page.
- Changed: `dashboard.html` only.
- Result: added live-games-focus above fold, changed default active secondary tab away from trade log, kept trade log secondary.
- Evidence: DOM/default-state changes, not just styling.
- Next step: restore baseball-monitor-first feel on main active object.

### DASHBOARD_LIVE_GAME_MONITOR_001
- Attempted: improve live monitoring/accounting/game focus.
- Changed: `dashboard.html` plus tiny `dashboard_server.py` accounting field additions.
- Result: accounting strip with available cash/capital committed/live equity; cards more live-monitor-oriented.
- Evidence: new bankroll fields, hybrid monitoring emphasis.
- Next step: stronger baseball-monitor restore, because user reported the page still felt too log-first.

### DASHBOARD_RESTORE_BASEBALL_MONITOR_001
- Attempted: restore older baseball-monitor feel while keeping new truth/accounting semantics.
- Changed: `dashboard.html` only.
- Result: main active card now baseball-monitor-first with score, inning, outs, bases, pitcher, and trade/accounting block.
- Evidence: focused monitor card restored with baseball-state prominence.
- Next step: build fresh V2 shell side-by-side.

### DASHBOARD_V2_001
- Attempted: from-scratch `dashboard_v2.html` side-by-side build.
- Changed: created `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_v2.html` plus BOT_BRIDGE task/handoff/result/review.
- Result: fresh game-first shell with command bar, live monitor, accounting strip, live games rail, and secondary shadow/trade log.
- Evidence: V2 file created without modifying production dashboard.
- Next logical step: verification-only pass on V2 wiring and usability before any Claude polish.
