# AUDIT_DASHBOARD_EXPOSE_RUNTIME_VITALS_001

- run: `RUN_CB37474E9ACD`
- role: `OPUS_AUDITOR`
- kind: `auditor`
- verdict: `INDETERMINATE`

## RESULT_JSON

```json
{
  "status": "ok",
  "summary": "Dashboard already renders 6/8 acceptance items in the SYSTEM tab of dashboard.html; gaps are unrendered mode.multipliers + mode.switch_reason, unrendered session_start_ts, missing per-window pnl in rolling cards, and missing market_validity_blocks + last_invalid_market_details. Canonical file is dashboard.html; dashboard_v2.html needs no edits. No server-side changes required."
}
```

## Transcript tail

```
[system]
[system]
[session] id=a74ce010 model=claude-opus-4-7
I'll perform this audit read-only. Reading the three allowed files to compare `/api/state` payload vs. what the dashboard actually renders.
[tool→ Read] file_path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard_server.py
[tool← 47300B] 1	"""
[tool→ Read] file_path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
[tool← 204B] File content (47792 tokens) exceeds maximum allowed tokens (25000). Use offset and limit parameters to read specific portions of the file, or search for specific content instead of reading the whole …
[tool→ Read] file_path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard_v2.html
[tool← 20764B] 1	<!DOCTYPE html>
`dashboard_v2.html` is a complete file (128 lines). Now let me understand `dashboard.html` by scanning it.
[tool→ Bash] command=wc -l "C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html"
[tool← 57B] 1870 C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
[tool→ Grep] path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
[tool← 6156B] 418:    <span class="cmdbar-stat">Bankroll: <b id="kpi-bankroll">$—</b></span>
The HTML already contains substantial render code. Let me inspect which DOM containers exist and what actually wires to `/api/state`.
[tool→ Grep] path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
[tool← 718B] 531:          <div id="system-freshness" class="cash-strip"></div>
[tool→ Read] file_path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
[tool← 12611B] 1520	    </div>`;
Let me verify which DOM containers are actually present for all the rendered sections.
[tool→ Grep] path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
[tool← 55B] 528:      <section id="tab-system" class="shell-panel">
[tool→ Grep] path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
[tool← 426B] 1371:  $('thr-conf').textContent   = thr.min_confidence ? (thr.min_confidence*100).toFixed(0)+'%' : '—';
[tool→ Read] file_path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
[tool← 4334B] 500	          <div class="section-header"><span class="section-title">Recently closed</span></div>
All 8 sections ARE already implemented. Let me verify gaps (multipliers, switch_reason, session_start_ts) and which tab is default.
[tool→ Grep] path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
[tool← 513B] 429:    <button class="tab-btn active" onclick="switchTab('live',this)">LIVE</button>
[tool→ Grep] path=C:\Users\johnny\Desktop\sports_bot_v2\dashboard.html
[tool← 123B] 1591:  const session_start = bankroll.session_start_ts ? new Date(bankroll.session_start_ts * 1000).toLocaleString() : '—';
I have enough evidence. Writing the audit file now.
[tool→ Write] file_path=C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\08_SHARED_CONTEXT\AUDIT_DASHBOARD_EXPOSE_RUNTIME_VITALS_001.md
[tool← 200B] File created successfully at: C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\08_SHARED_CONTEXT\AUDIT_DASHBOARD_EXPOSE_RUNTIME_VITALS_001.md (file state is current in your context — no need to Read it back)
Audit filed at `BOT_BRIDGE/08_SHARED_CONTEXT/AUDIT_DASHBOARD_EXPOSE_RUNTIME_VITALS_001.md`.

**Findings summary:**
- Canonical file: `dashboard.html` (served at `/`). `dashboard_v2.html` is a minimal alternate at `/v2`.
- The `#tab-system` panel (dashboard.html:528-561) already contains all 8 acceptance sections with containers and a `renderSystemTab` function (1533-1641).
- **6 of 8 items render cleanly**: freshness, rolling r25/r50/r100, guard block rate+reasons, bankroll, recent closed trades, exit counts, cooldowns, lifetime (total_trades/loop/config_hash).
- **Gaps (pure template edits in dashboard.html)**:
  1. `mode.multipliers` computed (line 1583) but never rendered; `mode.switch_reason` never referenced.
  2. `session_start` computed (line 1591) but never emitted.
  3. `w.pnl` not shown in rolling window cards.
  4. `market_validity_blocks` + `last_invalid_market_details` not rendered.
  5. (Optional/symptom-fix.) Default tab is LIVE — `guard_block_rate` is not in the top bar, so the 100%-block symptom remains tab-gated.
- No `dashboard_server.py` edits needed; payload already carries every field.

RESULT_JSON: {"status":"ok","summary":"Dashboard already renders 6/8 acceptance items in the SYSTEM tab of dashboard.html; gaps are unrendered mode.multipliers + mode.switch_reason, unrendered session_start_ts, missing per-window pnl in rolling cards, and missing market_validity_blocks + last_invalid_market_details. Canonical file is dashboard.html; dashboard_v2.html needs no edits. No server-side changes required."}
[done] ok duration=130890ms turns=14
[usage] input=12 output=9022 cache_read=416221 cost_usd=0.8475
```
