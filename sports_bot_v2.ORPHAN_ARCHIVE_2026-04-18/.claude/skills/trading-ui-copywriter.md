# Skill: Trading UI Copywriter

Label and copy conventions for this dashboard.

## Stat labels (monospace uppercase, 8-9px)
| Data | Label |
|------|-------|
| Shadow P&L in units | `Shadow P&L` |
| Shadow win rate | `Win Rate` |
| Unresolved recs count | `Active` |
| Resolved recs count | `Resolved` |
| Bot bankroll | `Bankroll` |
| Rolling 25-trade win rate | `Win Rate R25` |
| Bot open positions count | `Open` |
| Bot realized P&L | `Net P&L` |
| Per-trade expectancy | `Expectancy` |
| Live ESPN games | `Live Games` |
| Candidate minimum confidence | `min conf` |
| Candidate maximum spread | `max spread` |
| Candidate minimum depth | `min depth` |

## Action badges
- `BUY YES` (not "BUY_YES") — green pill
- `BUY NO` (not "BUY_NO") — red pill

## Status badges
- `● LIVE` — green, for unresolved active position
- `✓ WON` — green, for resolved win
- `✗ LOST` — red, for resolved loss
- `pending` — muted, for unresolved shadow rec in feed

## Signal strength labels
- `STRONG` (green) — conf ≥ 0.72
- `MODERATE` (gold) — conf ≥ 0.62
- `WEAK` (red) — below 0.62

## Tab names
Trade Log | Candidates | Markets | Signals | Manual

## Section titles
Active Positions | Shadow Feed | Live Games | Bot Open Positions | Guard Stack | Manual Trade Entry

## Avoid
- "No open positions" → use "No active shadow positions" for shadow section
- "bot offline" is fine, but show stale time: `stale 45s`
- Don't show raw field names like `edge_yes`, `ask_no` — translate to "Edge", "Entry"
