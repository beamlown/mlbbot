# CLAUDE_STATUS_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_STATUS.md`.

## Add under Completed This Reconciliation Pass
| MIN_ENTRY_PRICE_GATE_001 | APPROVED — minimum entry-price floor added to `check_entry_gates()` in `core/risk.py`; correct side-specific ask handling; `py_compile` PASS; restart required. |
| TP_NEAR_RESOLUTION_CAP_FIX_001 | APPROVED — near-resolution TP now capped in `core/risk.py` so near-1.0 entries cannot compute unreachable TP values above the contract ceiling; `py_compile` PASS; restart required. |
| BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001 | APPROVED — per-loop consumed-slug guard added in `bot_core.py` so repeated slug intents cannot re-enter later in the same bridge iteration; `py_compile` PASS; restart required. |

## Replace the ultra-low-price paragraph with:
- **Ultra-low-price entry bug: patched, verify pending** — `MIN_ENTRY_PRICE_GATE_001` is approved. The risk pipeline now includes a minimum entry price floor (default 0.15) intended to block the 0.05–0.07 entry churn that caused instant stop-loss exits. Restart is required before this protection is live.

## Replace the near-resolution TP paragraph with:
- **Near-resolution TP bug: patched, verify pending** — `TP_NEAR_RESOLUTION_CAP_FIX_001` is approved. The TP pipeline now caps unreachable TP values for near-1.0 entries. Restart is required before this protection is live.

## Replace the duplicate-slug paragraph with:
- **Duplicate-slug gate bug: patched, verify pending** — `BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001` is approved. The bridge loop now consumes a slug once per iteration so repeated instances cannot bypass protections later in the same loop. Restart is required before this protection is live.

## Update Open Items section
Replace or add:
| **Market cooldown persistence** | HIGH | Cooldown is still in-memory only and restarts wipe it. `MARKET_COOLDOWN_PERSIST_001` is now ACTIVE. |
| **Session PnL true-start fix** | MEDIUM | Still queued behind the remaining critical cooldown persistence work. |
| **Side-semantics regression audit** | MEDIUM | Still queued behind the remaining critical risk tasks. |

## Keep unchanged for now
- pycache delete + cold restart remains operator-critical
- user/fill stream credentials remain blocked on Johnny
