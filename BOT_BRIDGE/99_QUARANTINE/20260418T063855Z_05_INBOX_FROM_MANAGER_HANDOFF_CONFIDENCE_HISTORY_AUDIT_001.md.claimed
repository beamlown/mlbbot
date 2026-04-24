# HANDOFF — CONFIDENCE_HISTORY_AUDIT_001
**Priority:** HIGH
**Type:** Read-only audit
**Issued:** 2026-04-10

---

## One-sentence task

Audit recent recommendation and trade confidence values to determine whether the new `MIN_ENTRY_CONFIDENCE=0.60` hard floor would materially reduce trade frequency.

---

## What you are answering

> Would the new 0.60 gate have blocked most recent recommendations/trades, or are there enough signals at or above 0.60 for the bot to still trade normally?

---

## What you must NOT do

- Edit any code
- Edit .env
- Write to the DB (SELECT only)
- Restart any process
- Touch dashboard.html, dashboard_server.py, bot_core.py, launch_all.py, core/risk.py, core/paper_exec.py
- Do a broad repo sweep

---

## Where to look (in order)

1. **sports_bot_v2 logs** — look for log lines containing `confidence`
2. **mlb_model output or recommendation logs** — look for emitted confidence values
3. **trades_sports.db** — only if confidence is actually stored as a column (SELECT query only)
4. **Code** — read only 1–2 files max to locate the confidence field/log call if needed

---

## Required output

Write your result to:

```
C:\Users\johnny\Desktop\BOT_BRIDGE\06_OUTBOX_FROM_WORKER\RESULT_CONFIDENCE_HISTORY_AUDIT_001.json
```

The result must include:

1. **Sample window** — exact timestamps, exact N records
2. **Distribution** — counts in bins: <0.50, 0.50–0.549, 0.55–0.599, 0.60–0.649, 0.65–0.699, 0.70+
3. **Floor impact** — % pass, % fail against 0.60; lightly/moderately/heavily reduced
4. **Trade list** — last 10–25 trades with confidence if available
5. **Rec list** — last N recommendations with confidence if available
6. **Conclusion** — is 0.60 realistic? If not, what floor is?

Also state explicitly:
- Where confidence is stored/logged (exact path or DB column)
- Whether you used recommendation history, trade history, or both
- Whether any confidence data was missing

---

## Read TASK_CONFIDENCE_HISTORY_AUDIT_001.json for full acceptance criteria.
