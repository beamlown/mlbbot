# LAST 3 DAYS STILL NEEDS DONE

## MUST FIX

### 1. Prove or correct current `r25` behavior in dashboard server
- Why it is still not proven/complete: `DASH_014` claimed null-safe `r25` behavior, but current `dashboard_server.py` returns `0.0`/zeroed fallback on empty or error, which does not match the original task spec or its stated verification expectations.
- Exact likely files involved: `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- Should it be done before anything else: yes

### 2. Re-audit duplicate-entry protection against the live DB, not just source code
- Why it is still not proven/complete: `DUPLICATE_ENTRY_FIX_001` code exists now, but the verification chain showed live duplicate behavior and a missing live DB unique index during the incident. Current source alone does not prove the production DB is protected today.
- Exact likely files involved: `C:\Users\johnny\Desktop\sports_bot_v2\core\db.py`, `C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py`, live DB at `C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db`
- Should it be done before anything else: yes

### 3. Finish the unresolved dashboard truth task chain
- Why it is still not proven/complete: `DASHBOARD_TRUTH_002` appears opened but not actually completed/proven in the audited artifacts, while several dashboard truth changes were implemented piecemeal through other tasks.
- Exact likely files involved: `C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_DASHBOARD_TRUTH_002.json`, `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`, possibly `C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py`
- Should it be done before anything else: yes

## SHOULD FIX

### 4. Reconcile current position-card stats with DASH_015 deliverable history
- Why it is still not proven/complete: current cards no longer match the reviewed 6-box layout exactly because they now include `Committed` and `Live Equity`, so historical completion of DASH_015 is only partial in present-day code.
- Exact likely files involved: `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- Should it be done before anything else: no

### 5. Reconcile current empty-state copy with SYSTEM_UNIFY_001 claims
- Why it is still not proven/complete: the review claimed a specific "No open positions" truth state, but current code shows a more expanded "No live paper positions right now" message.
- Exact likely files involved: `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`
- Should it be done before anything else: no

### 6. Separate style/polish task proof from later merged dashboard edits
- Why it is still not proven/complete: `DASHBOARD_POLISH_001`, `DASHBOARD_STYLE_FUN_001`, and `DASHBOARD_HIERARCHY_FIX_001` have artifacts, but current file state is too merged to prove their exact claimed deliverables cleanly.
- Exact likely files involved: `C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html`, corresponding BOT_BRIDGE task/result/review files
- Should it be done before anything else: no

## NICE TO HAVE

### 7. Normalize audit/result naming for verification-only tasks
- Why it is still not proven/complete: several verification and incident tasks are effectively complete as investigations, but their statuses mix `blocked`, `done_partial`, and provisional review states in ways that make later proof-of-work auditing harder.
- Exact likely files involved: `C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_VERIFY_DUPLICATE_ENTRY_001.json`, `C:\Users\johnny\Desktop\BOT_BRIDGE\05_INBOX_FROM_MANAGER\TASK_INCIDENT_*`, related result/review files
- Should it be done before anything else: no
