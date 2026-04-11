# CLAUDE_STATUS_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_STATUS.md`.

## Add under Completed This Reconciliation Pass
| MARKET_COOLDOWN_PERSIST_001 | APPROVED — `bot_core.py` now persists non-expired cooldown expiries to runtime state and reloads them on startup; `py_compile` PASS; restart required. |

## Replace the market cooldown paragraph with:
- **Market cooldown persistence: patched, verify pending** — `MARKET_COOLDOWN_PERSIST_001` is approved. The bot now persists active cooldown expiries into runtime state and restores them at startup so restarts no longer wipe cooldown protection. Restart is required before this protection is live, and stale bot_core pycache must still be cleared.

## Update Open Items section
Replace or add:
| **Session PnL true-start fix** | MEDIUM | Session PnL still follows restart timing instead of true trading session start. `SESSION_PNL_TRUE_START_FIX_001` is now ACTIVE. |
| **Side-semantics regression audit** | MEDIUM | Still queued behind the remaining visibility/session fix. |

## Keep unchanged for now
- pycache delete + cold restart remains operator-critical
- user/fill stream credentials remain blocked on Johnny
