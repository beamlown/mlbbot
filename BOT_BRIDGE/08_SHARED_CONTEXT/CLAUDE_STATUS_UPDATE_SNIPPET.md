# CLAUDE_STATUS_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_STATUS.md`.

## Add under Completed This Reconciliation Pass
| MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001 | APPROVED — fallback gate tightened in `dashboard_server.py`; fresh stream marks should remain primary; restart completed. |

## Replace the confidence gate paragraph with:
- **Confidence gate: LIVE REBREAK SUSPECTED** — Current runtime now shows three new open trades below the intended 0.60 floor: trade 241 (0.3863), trade 243 (0.3279), and trade 244 (0.3769). This is newer than the prior postfix verify chain and indicates the live confidence gate is still not reliably protecting entries. `CONFIDENCE_GATE_LIVE_REBREAK_001` is now ACTIVE to identify the current bypass or runtime mismatch.

## Replace the dashboard display issues paragraph with:
- **Display issues — fallback patched, side-truth regression now under live audit** — `MARK_SOURCE_FALLBACK_RELIABILITY_FIX_001` was approved and restarted, but the operator is now reporting that the dashboard sometimes shows the bot backing the wrong team. `POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001` is ACTIVE to trace one or more current live positions from execution truth through payload mapping to card semantics.

## Update Open Items section
Replace the old pyc/restart item with:
| **Confidence gate live rebreak** | HIGH | New runtime evidence shows trades 241/243/244 opened below 0.60 after restart. `CONFIDENCE_GATE_LIVE_REBREAK_001` ACTIVE. |

Add:
| **Side-semantics regression** | HIGH | Operator reports dashboard sometimes shows the wrong backed team. `POSITION_SIDE_SEMANTICS_REGRESSION_AUDIT_001` ACTIVE. |

## Keep unchanged for now
- `BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001` is still likely needed
- user/fill stream credentials remain blocked on Johnny
