# CLAUDE_STATUS_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_STATUS.md`.

## Add under Completed This Reconciliation Pass
| BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 | APPROVED — per-loop consumed-slug guard added in `bot_core.py` so repeated slug intents cannot re-enter later in the same bridge iteration; `py_compile` PASS; restart required. |

## Replace the relevant risk/open-item paragraph with:
- **Duplicate-slug gate bug: patched, verify pending** — `BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001` is approved. The bridge loop now consumes a slug once per iteration so repeated instances cannot bypass protections later in the same loop. Restart is required before this protection is live.

## Update Open Items section
Add or replace with:
| **Market cooldown persistence** | HIGH | Cooldown is still in-memory only and restarts wipe it. `MARKET_COOLDOWN_PERSIST_001` is now ACTIVE. |

Keep unchanged for now
- pycache delete + cold restart remains operator-critical
- session PnL true-start fix still queued
- side-semantics audit still queued behind critical risk items
