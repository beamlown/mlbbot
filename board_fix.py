import re

path = "C:/Users/johnny/Desktop/mlbbot/BOT_BRIDGE/08_SHARED_CONTEXT/CLAUDE_TASK_BOARD.md"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

orig_len = len(content)

# The previous script removed MLB_CONFIDENCE_CALIBRATION from ACTIVE (step 5 regex matched it).
# Fix: insert the missing row after MLB_PITCHER row in ACTIVE section.

target = (
    "| MLB_PITCHER_BULLPEN_HYDRATION_BUILD_001 | Populate pitcher_game_logs and bullpen_context in the canonical 2026 MLB foundation | HIGH | mlb_model pitcher/bullpen hydration completion |"
)

calibration_row = (
    "\n| MLB_CONFIDENCE_CALIBRATION_AUDIT_001 | Audit whether MLB model confidence is calibrated, inverted, noisy, or structurally invalid | HIGH | mlb_model confidence / outcome linkage | "
    "`C:\\Users\\johnny\\Desktop\\mlb_model\\integration\\recommendation_api.py`, "
    "`C:\\Users\\johnny\\Desktop\\sports_bot_v2\\core\\model_bridge.py`, "
    "`C:\\Users\\johnny\\Desktop\\mlb_model\\logs\\shadow_recommendations.jsonl`, "
    "`C:\\Users\\johnny\\Desktop\\sports_bot_v2\\trades_sports.db` | "
    "**PROMOTED from QUEUED** - critical path: clean-era n=0 trades; model calibration must be understood before trading resumes. Read-only. No conflict with pitcher task. |"
)

# Find the pitcher row's end (end of that line) and insert after it
pitcher_line_end = content.find('\n', content.find(target))
if pitcher_line_end >= 0 and "MLB_CONFIDENCE_CALIBRATION_AUDIT_001" not in content[content.find("## ACTIVE"):content.find("## QUEUED")]:
    content = content[:pitcher_line_end] + calibration_row + content[pitcher_line_end:]
    print("Inserted MLB_CONFIDENCE_CALIBRATION_AUDIT_001 into ACTIVE section.")
else:
    print("No insertion needed (already present or pitcher row not found).")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Content length: {orig_len} -> {len(content)}")

# Verify
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

active_section = c[c.find('## ACTIVE'):c.find('## QUEUED')]
active_rows = [l for l in active_section.split('\n') if l.startswith('|') and 'task_id' not in l and '---' not in l]
print(f"ACTIVE rows: {len(active_rows)}")
for r in active_rows:
    print(f"  {r[:100]}")
