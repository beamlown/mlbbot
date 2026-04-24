# AUDIT_CONFIDENCE_GATE_RUNTIME_VERIFY_001

- run: `RUN_047F952C47BB`
- role: `OPUS_AUDITOR`
- kind: `auditor`
- verdict: `FAIL`

## RESULT_JSON

```json
{
  "status": "ok",
  "summary": "Bridge uses check_entry_gates; risk.py hard-first MIN_ENTRY_CONFIDENCE; env=0.65. Trades 223/224 were post-restart (2026-04-10 17:28:59 ET) with confidences 0.3353/0.3996, unblocked \u2014 historical bug real. Current runtime logs show 0.65 floor firing correctly; live enforcement healthy."
}
```

## Transcript tail

```
[system]
[system]
[session] id=01cf0ef5 model=claude-opus-4-7
Starting audit. The handoff file and several allowed files are flagged as NOT FOUND — I'll verify their actual existence before emitting blocked status, then read the code files that are confirmed available.
[tool→ Bash] command=ls -la "C:/Users/johnny/Desktop/mlbbot/BOT_BRIDGE/05_INBOX_FROM_MANAGER/HANDOFF_CONFIDENCE_GATE_RUNTIME_VERIFY_001.md" 2>&1; ls -la "C:/Users/johnny/Desktop/sports_bot_v2/.env" 2>&1; ls -la "C:/Users…
[tool→ Bash] command=ls "C:/Users/johnny/Desktop/sports_bot_v2/"*.log 2>&1 | head -20; ls "C:/Users/johnny/Desktop/sports_bot_v2/logs/" 2>&1 | head -20
[rate-limit] status=allowed_warning
[tool← 569B] ls: cannot access 'C:/Users/johnny/Desktop/sports_bot_v2/*.log': No such file or directory
[tool← 448B] -rw-r--r-- 1 johnny 197121 1323 Apr 18 01:55 C:/Users/johnny/Desktop/mlbbot/BOT_BRIDGE/05_INBOX_FROM_MANAGER/HANDOFF_CONFIDENCE_GATE_RUNTIME_VERIFY_001.md
All files exist. Reading handoff and code now.
[tool→ Read] file_path=C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\05_INBOX_FROM_MANAGER\HANDOFF_CONFIDENCE_GATE_RUNTIME_VERIFY_001.md
[tool← 1402B] 1	# HANDOFF_CONFIDENCE_GATE_RUNTIME_VERIFY_001
[tool→ Read] file_path=C:\Users\johnny\Desktop\sports_bot_v2\core\risk.py
[tool← 14811B] 1	"""
[tool→ Read] file_path=C:\Users\johnny\Desktop\sports_bot_v2\core\model_bridge.py
[tool← 9315B] 1	from __future__ import annotations
Now reading bot_core.py (to check bridge uses check_entry_gates), .env, and querying DB.
[tool→ Read] file_path=C:\Users\johnny\Desktop\sports_bot_v2\bot_core.py
[tool← 42077B] 1	"""
[tool→ Read] file_path=C:\Users\johnny\Desktop\sports_bot_v2\.env
[tool← 4290B] 1	# ── Sport selection ─────────────────────────────────────────────────────────
[tool→ Bash] command=cd "C:/Users/johnny/Desktop/sports_bot_v2" && python -c " ⏎ import sqlite3 ⏎ c = sqlite3.connect('trades_sports.db') ⏎ cur = c.execute('PRAGMA table_info(trades)') ⏎ cols = [r[1] for r in cur.fetchal…
[tool← 2702B] COLUMNS: ['id', 'ts_open', 'ts_close', 'market_slug', 'market_id', 'side', 'qty', 'entry_px', 'exit_px', 'pnl_usd', 'fees_usd', 'reason_open', 'reason_close', 'confidence', 'mode', 'status', 'sport',…
Trades found — both have confidence <0.40, well under 0.60/0.65 floor. Now I need to verify restart time via logs to decide BEFORE/AFTER verdict.
[tool→ Bash] command=ls -la "C:/Users/johnny/Desktop/sports_bot_v2/logs/bot_baseball_20260410.log" "C:/Users/johnny/Desktop/sports_bot_v2/logs/bot_baseball_2026041"*.log 2>&1 | head -20
[tool← 471B] -rw-r--r-- 1 johnny 197121  2744237 Apr 11 00:00 C:/Users/johnny/Desktop/sports_bot_v2/logs/bot_baseball_20260410.log
[tool→ Grep] path=C:\Users\johnny\Desktop\sports_bot_v2\logs\bot_baseball_20260410.log
[tool← 3197B] 2:2026-04-09 23:13:10,573 [INFO] bot_core:   sports_bot_v2 starting — sport=baseball build=sports_bot_v2.baseball.2026-03-29
[tool→ Grep] path=C:\Users\johnny\Desktop\sports_bot_v2\logs\bot_baseball_20260410.log
[tool← 16B] No matches found
[tool→ Grep] path=C:\Users\johnny\Desktop\sports_bot_v2\logs\bot_baseball_20260410.log
[tool← 14121B] 2:2026-04-09 23:13:10,573 [INFO] bot_core:   sports_bot_v2 starting — sport=baseball build=sports_bot_v2.baseball.2026-03-29
Checking most recent startup log to verify current runtime state, and git blame on critical lines.
[tool→ Grep] path=C:\Users\johnny\Desktop\sports_bot_v2\logs\bot_baseball_20260418.log
[tool→ Bash] command=cd "C:/Users/johnny/Desktop/sports_bot_v2" && git log --oneline -20 -- core/risk.py bot_core.py 2>&1; echo "---"; git log --all --oneline --follow -- core/risk.py 2>&1 | head -30
[tool← 1870B] 2:2026-04-17 19:28:16,820 [INFO] bot_core:   sports_bot_v2 starting — sport=baseball build=sports_bot_v2.baseball.2026-03-29
[tool← 841B] 342199e AUTHORITY_SEPARATION_CLEANUP_001: isolate bot_core cleanup and task artifacts
All evidence gathered. Writing audit report now.
[tool→ Write] file_path=C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\08_SHARED_CONTEXT\AUDIT_CONFIDENCE_GATE_RUNTIME_VERIFY_001.md
[tool← 199B] File created successfully at: C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\08_SHARED_CONTEXT\AUDIT_CONFIDENCE_GATE_RUNTIME_VERIFY_001.md (file state is current in your context — no need to Read it back)
Audit written to `BOT_BRIDGE/08_SHARED_CONTEXT/AUDIT_CONFIDENCE_GATE_RUNTIME_VERIFY_001.md`.

**Key findings:**
- Bridge path uses `check_entry_gates()` — YES (`bot_core.py:632-642`)
- `0.60` floor loaded in live code/env — YES (env sets `0.65`, stricter; `risk.py:165-168` hard-first check)
- Trades 223/224 opened 2026-04-10 17:44 ET & 17:47 ET, both AFTER the 17:28:59 ET restart, at confidences 0.3353 and 0.3996 — neither was rejected, confirming a real historical bug at that time
- Current live runtime (restarts at 2026-04-17 19:28 ET and 2026-04-18 00:46 UTC) actively rejects sub-0.65 bridge entries; enforcement is healthy

RESULT_JSON: {"status":"ok","summary":"Bridge uses check_entry_gates; risk.py hard-first MIN_ENTRY_CONFIDENCE; env=0.65. Trades 223/224 were post-restart (2026-04-10 17:28:59 ET) with confidences 0.3353/0.3996, unblocked — historical bug real. Current runtime logs show 0.65 floor firing correctly; live enforcement healthy."}
[done] ok duration=184617ms turns=16
[usage] input=330 output=12854 cache_read=443871 cost_usd=1.0068
```
