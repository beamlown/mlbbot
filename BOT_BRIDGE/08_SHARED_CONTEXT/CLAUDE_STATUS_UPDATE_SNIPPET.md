# CLAUDE_STATUS_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_STATUS.md`.

## Add under Completed This Reconciliation Pass
| TP_NEAR_RESOLUTION_CAP_FIX_001 | APPROVED — near-resolution TP now capped in `core/risk.py` so near-1.0 entries cannot compute unreachable TP values above the contract ceiling; `py_compile` PASS; restart required. |

## Replace the relevant risk/open-item paragraph with:
- **Near-resolution TP bug: patched, verify pending** — `TP_NEAR_RESOLUTION_CAP_FIX_001` is approved. The TP pipeline now caps unreachable TP values for near-1.0 entries. Restart is required before this protection is live.

## Update Open Items section
Add or replace with:
| **Duplicate-slug bridge gate fix** | HIGH | Repeated intents for the same slug can still bypass protections within a bridge loop. `BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001` is now ACTIVE. |

Keep unchanged for now
- pycache delete + cold restart remains operator-critical
- market cooldown persistence still queued
- session PnL true-start fix still queued
- side-semantics audit still queued behind critical risk items
