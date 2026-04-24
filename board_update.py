import re

path = "C:/Users/johnny/Desktop/mlbbot/BOT_BRIDGE/08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

orig_len = len(content)

# 1. Replace entire ACTIVE section
new_active = """## ACTIVE

| task_id | title | priority | subsystem | allowed_files | notes |
|---------|-------|----------|-----------|---------------|-------|
| MLB_PITCHER_BULLPEN_HYDRATION_BUILD_001 | Populate pitcher_game_logs and bullpen_context in the canonical 2026 MLB foundation | HIGH | mlb_model pitcher/bullpen hydration completion | `C:\\Users\\johnny\\Desktop\\mlb_model\\scripts\\**`, `C:\\Users\\johnny\\Desktop\\mlb_model\\data\\foundation\\mlb_statsapi\\season=2026\\**`, `C:\\Users\\johnny\\Desktop\\BOT_BRIDGE\\08_SHARED_CONTEXT\\MLB_STATS_FOUNDATION_SPEC_001.md`, `C:\\Users\\johnny\\Desktop\\BOT_BRIDGE\\06_OUTBOX_FROM_WORKER\\RESULT_MLB_CURRENT_SEASON_BACKFILL_BUILD_001.json`, `C:\\Users\\johnny\\Desktop\\BOT_BRIDGE\\06_OUTBOX_FROM_WORKER\\RESULT_MLB_BACKFILL_HYDRATION_GAP_FIX_001.json` | Prior run SIGKILL terminated before completion. Needs chunked execution strategy. Paper-only / observation mode. |
| MLB_CONFIDENCE_CALIBRATION_AUDIT_001 | Audit whether MLB model confidence is calibrated, inverted, noisy, or structurally invalid | HIGH | mlb_model confidence / outcome linkage | `C:\\Users\\johnny\\Desktop\\mlb_model\\integration\\recommendation_api.py`, `C:\\Users\\johnny\\Desktop\\sports_bot_v2\\core\\model_bridge.py`, `C:\\Users\\johnny\\Desktop\\mlb_model\\logs\\shadow_recommendations.jsonl`, `C:\\Users\\johnny\\Desktop\\sports_bot_v2\\trades_sports.db` | **PROMOTED from QUEUED** - critical path: clean-era n=0 trades; model calibration must be understood before trading resumes. Read-only. No conflict with pitcher task. |

*(Slot 3 reserved - Haiku worker failure incident 2026-04-17. Do not re-issue failed tasks until failure mode diagnosed.)*"""

content = re.sub(
    r'## ACTIVE\n.*?(?=\n---\n\n## QUEUED)',
    lambda m: new_active,
    content,
    flags=re.DOTALL
)

# 2. Fix empty DONE outcomes (using unicode em-dash as in file)
content = content.replace(
    '| CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001 | Trace runtime code/version/process identity for low-confidence live opens |  |',
    '| CONFIDENCE_GATE_RUNTIME_VERSION_TRACE_001 | Trace runtime code/version/process identity for low-confidence live opens | APPROVED 2026-04-17 - Root cause confirmed: stale background process with pre-update .env + 4-day-old model_bridge.pyc. .env rewritten at 10:46 UTC (10h after trades). Clean restart at 10:57:33 resolved. No code defect in on-disk files. |',
    1
)

content = content.replace(
    '| CONFIDENCE_GATE_LIVE_REBREAK_001 | Re-verify live confidence gate after restart and identify current bypass path |  |',
    '| CONFIDENCE_GATE_LIVE_REBREAK_001 | Re-verify live confidence gate after restart and identify current bypass path | CLOSED 2026-04-17 - Worker failed (Haiku incident). Answered by REBREAK_TRACE_002 + RUNTIME_VERSION_TRACE_001: root cause was runtime divergence (stale process + old .env). Code correct since Apr 11 10:57 restart. |',
    1
)

# 3. Add DONE entries for newly closed tasks - insert before MODEL_SIGNAL_QUALITY
new_done_block = (
    "| CONFIDENCE_GATE_LIVE_REBREAK_FIX_001 | Fix live confidence gate rebreak | CLOSED 2026-04-17 - No fix needed. On-disk bot_core.py already correct. Bug was runtime divergence, not a code defect. | `C:\\Users\\johnny\\Desktop\\sports_bot_v2\\bot_core.py` |\n"
    "| CONFIDENCE_GATE_LIVE_REBREAK_TRACE_002 | Trace exact live open path for current confidence-gate rebreak | APPROVED 2026-04-17 - Runtime divergence confirmed. On-disk bridge path clean: failed gates already continue before open_position(). No second open path found. | `C:\\Users\\johnny\\Desktop\\sports_bot_v2\\bot_core.py`, `core\\model_bridge.py`, `core\\risk.py` |\n"
    "| MLB_STATS_FOUNDATION_SPEC_001 | Define the canonical raw-data foundation for current-season MLB rebuild work | APPROVED 2026-04-17 - Ratified by downstream consumption: MLB_CURRENT_SEASON_BACKFILL_BUILD_001 ran against it. | `BOT_BRIDGE\\08_SHARED_CONTEXT\\MODEL_REBUILD_TRACK_001.md`, result artifacts |\n"
    "| MLB_MODEL_INPUT_PATH_AUDIT_001 | Trace exactly what features and game/market context reach the model today | APPROVED 2026-04-17 - Ratified by downstream consumption: consumed by MLB_STATS_FOUNDATION_SPEC_001 chain. | `mlb_model\\integration\\recommendation_api.py`, `sports_bot_v2\\core\\model_bridge.py` |\n"
    "| MLB_DATA_INVENTORY_AUDIT_001 | Inventory all existing MLB model data and artifacts | APPROVED 2026-04-17 - Ratified by downstream consumption: consumed by MLB_DATA_GAP_MAP_001 and spec chain. | `mlb_model\\**`, `sports_bot_v2\\trades_sports.db` |\n"
    "| MLB_BACKFILL_HYDRATION_GAP_FIX_001 | Fix missing pitcher/bullpen hydration and enforce season-to-date coverage | PARTIAL APPROVED 2026-04-17 - Manifest boundary corrected. pitcher_game_logs and bullpen_context population transferred to MLB_PITCHER_BULLPEN_HYDRATION_BUILD_001. | `C:\\Users\\johnny\\Desktop\\mlb_model\\scripts\\**`, `mlb_model\\data\\foundation\\mlb_statsapi\\season=2026\\**` |\n"
    "| MODEL_SIGNAL_QUALITY_AUDIT_001 | Audit model confidence calibration"
)

if "| MODEL_SIGNAL_QUALITY_AUDIT_001 | Audit model confidence calibration" in content:
    content = content.replace(
        "| MODEL_SIGNAL_QUALITY_AUDIT_001 | Audit model confidence calibration",
        new_done_block,
        1
    )

# 4. Update Conflict Map - fix stale PAPER_BRIDGE_001 locks
em_dash = '\u2014'
for old_str, new_str in [
    (
        f"| bot_core.py | LOCKED {em_dash} PAPER_BRIDGE_001 (ACTIVE). Next: TRADE_FORENSICS_SNAPSHOT_001 (BACKLOG). Do not activate SESSION_SLUG_LOSS_CAP_001 or TRADE_FORENSICS_SNAPSHOT_001 while PAPER_BRIDGE_001 is active. |",
        "| bot_core.py | UNLOCKED - available for QUEUED tasks when slot 3 opens. Do not activate SESSION_SLUG_LOSS_CAP_001 and TRADE_FORENSICS_SNAPSHOT_001 simultaneously (both touch bot_core.py). |"
    ),
    (
        f"| core/model_bridge.py | LOCKED {em_dash} PAPER_BRIDGE_001 (ACTIVE). |",
        "| core/model_bridge.py | UNLOCKED |"
    ),
    (
        f"| core/market_stream.py, core/state_hub.py, dashboard_server.py, dashboard.html | LOCKED {em_dash} REALTIME_MARKET_STREAM_STAGE1_001 (ACTIVE). |",
        "| core/market_stream.py, core/state_hub.py, dashboard_server.py, dashboard.html | UNLOCKED - REALTIME_MARKET_STREAM_STAGE1_001 re-queued (Haiku failure). |"
    ),
    (
        f"| mlb_model/scripts/**, mlb_model/data/foundation/mlb_statsapi/season=2026/** | LOCKED {em_dash} MLB_PITCHER_BULLPEN_HYDRATION_BUILD_001 (ACTIVE). |",
        "| mlb_model/scripts/**, mlb_model/data/foundation/mlb_statsapi/season=2026/** | LOCKED - MLB_PITCHER_BULLPEN_HYDRATION_BUILD_001 (ACTIVE). |"
    ),
]:
    if old_str in content:
        content = content.replace(old_str, new_str, 1)

# 5. Remove MLB_CONFIDENCE_CALIBRATION_AUDIT_001 from bottom QUEUED (it's now in ACTIVE)
content = re.sub(
    r'\| MLB_CONFIDENCE_CALIBRATION_AUDIT_001 \| Audit whether MLB model confidence is calibrated[^\n]+\n',
    '',
    content,
    count=1
)

# 6. Remove CONFIG_HASH_INPUTS_FIX_001 from QUEUED (already done)
content = re.sub(
    r'\| CONFIG_HASH_INPUTS_FIX_001 \| Fix config hash inputs[^\n]+\n',
    '',
    content,
    count=1
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

new_len = len(content)
print(f"Board updated. Content length: {orig_len} -> {new_len} chars")

# Verify ACTIVE section
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

active_section = c[c.find('## ACTIVE'):c.find('## QUEUED')]
active_rows = [l for l in active_section.split('\n') if l.startswith('|') and 'task_id' not in l and '---' not in l]
print(f"ACTIVE rows: {len(active_rows)}")
for r in active_rows:
    print(f"  {r[:80]}")
