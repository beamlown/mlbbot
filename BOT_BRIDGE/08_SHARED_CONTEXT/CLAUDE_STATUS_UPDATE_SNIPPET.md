# CLAUDE_STATUS_UPDATE_SNIPPET.md

Use this to update `08_SHARED_CONTEXT/CLAUDE_STATUS.md`.

## Add under Completed This Reconciliation Pass
| CONFIDENCE_GATE_LIVE_REBREAK_001 | APPROVED — fresh live audit confirmed current runtime still opens sub-0.60 trades after restart; issue is not simple config drift but a live gate/open ordering inconsistency or bypass. |

## Replace the confidence gate paragraph with:
- **Confidence gate: LIVE REBREAK CONFIRMED** — New runtime evidence now shows fresh open trades below the intended 0.60 floor: trade 241 (0.3863), trade 243 (0.3279), and trade 244 (0.3769). The audit also found 0.600 reject evidence in the same live system, which rules out simple threshold/config drift. `CONFIDENCE_GATE_LIVE_REBREAK_FIX_001` is now ACTIVE to eliminate the current live gate/open inconsistency.

## Update Open Items section
Replace the confidence gate item with:
| **Confidence gate live rebreak fix** | HIGH | Current live runtime still opens sub-0.60 trades. `CONFIDENCE_GATE_LIVE_REBREAK_FIX_001` ACTIVE. |

Replace the side semantics item with:
| **Side-semantics regression audit** | MEDIUM | Still needed, but queued behind the confidence-gate live rebreak fix because the gate issue is the higher-risk live trading problem. |

## Keep unchanged for now
- `BRIDGE_ENTRY_GATE_DUPE_SLUG_FIX_001` may still be implicated
- user/fill stream credentials remain blocked on Johnny
