# BOT_BRIDGE — Start Here

This is the **canonical** bridge root. Everything under `C:\Users\johnny\Desktop\mlbbot\BOT_BRIDGE\` is the one source of truth.

The legacy tree at `C:\Users\johnny\Desktop\BOT_BRIDGE\` is a **frozen museum** after 2026-04-18. Touching it trips the control-plane startup guardrail and refuses to boot.

## Folder map

| Folder | Writer | Purpose |
|---|---|---|
| `00_START_HERE` | control_plane | This readme |
| `01_RULES` | operator | Doctrine (BOT_BRIDGE_OPERATING_PRINCIPLES + role rules) |
| `02_PROMPTS` | operator | Prompt scaffolds consumed by `control_plane\runner\prompts.py` |
| `03_TEMPLATES` | operator | TASK / RESULT / REVIEW / HANDOFF templates |
| `04_DRAFTS` | operator, manager | Pre-promotion scratchpad; control plane promotes to `05_INBOX` |
| `05_INBOX_FROM_MANAGER` | manager, control_plane | `HANDOFF_<TID>.md` + `TASK_<TID>.json` pairs |
| `06_OUTBOX_FROM_WORKER` | worker | `RESULT_<TID>.json` |
| `07_REVIEWS` | reviewer | `REVIEW_<TID>.md` starting with `DECISION: …` |
| `08_PATCHES` | auditor, control_plane | One subfolder per patch with manifest + `AUDIT_<PATCH>.md` |
| `08_SHARED_CONTEXT` | mixed (legacy scope) | Cross-cutting state, task board MD, audit indexes |
| `10_ARCHIVE` | control_plane | Auto-rotated from 05–08 after SHIPPED + N days |
| `99_QUARANTINE` | control_plane | Rogue / mis-placed / malformed files land here |

## The workflow in one picture

```
DRAFT → READY_FOR_WORKER → CLAIMED → RUNNING → AWAITING_REVIEW
                                                       │
        CHANGES_REQUESTED ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
                │                                      ▼
                └─→ READY_FOR_WORKER          APPROVED → IN_PATCH → SHIPPED → ARCHIVED
                                                 or BLOCKED (terminal)
```

Every transition is driven by exactly one legal trigger (file appearing in a specific folder, or a button in the control plane at http://127.0.0.1:8787). The control plane is the operator's only surface — do not mutate the filetree by hand except to drop drafts in `04_DRAFTS\`.

## Design spec

Authoritative reference: `docs\superpowers\specs\2026-04-18-bot-bridge-workflow-design.md`

## Writer-attribution header

Every artifact file begins with:

```
<!-- writer: <role_id>, task_id: <TID>, patch_id: <PID|pending>, written_at: <iso>, attempt: <n> -->
```

Mismatches (e.g. a file with `writer: worker` dropped in `07_REVIEWS`) get moved to `99_QUARANTINE\` on next import.
