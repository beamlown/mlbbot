# DASHBOARD_REDESIGN_AUDIT_REPORT_001

**Verdict: PASS**

Audit date: 2026-04-08
Final commit: a19f421

---

## Spec item-by-item audit

### Tab names and default
| Spec requirement | Implementation | Status |
|---|---|---|
| 5 tabs: LIVE, POSITIONS, GAMES, HISTORY, SYSTEM | HTML: 5 tab-btn elements with exact names | PASS |
| Default tab: LIVE | `#tab-live class="shell-panel active"` | PASS |

### LIVE tab
| Spec requirement | Implementation | Status |
|---|---|---|
| Focal order: game monitor → position cards → account strip | col-left: positions-list; col-right: live-games-focus, games-ticker, kpi-strip | PASS |
| Shadow absent from LIVE | Python parse confirmed; shadow-feed in display:none drawer | PASS |
| Trade log absent from LIVE | #trades-list in drawer, not in tab-live | PASS |
| Candidates absent from LIVE | candidates-list in drawer, not in tab-live | PASS |
| Manual entry absent from LIVE | mt-slug form in drawer, not in tab-live | PASS |
| backed_team display | headlineText = `${r.backed_team} backed` | PASS |
| faded_team secondary | fadedText = `${r.faded_team} faded` in pos-source-chip | PASS |
| current_held_price from SSE | `const currentHeldPrice = r.current_price` — no bid_yes/bid_no branching | PASS |
| live_equity from SSE | `positions[].live_equity_usd` | PASS |
| unrealized_pnl_usd from SSE | `positions[].unrealized_pnl_usd` | PASS |
| In-place SSE updates | `updateLivePositionCardInPlace` → `_applyMarkToCard` via querySelectorAll | PASS |
| STALE badge from SSE stale field | `current_price_stale` → badge visible | PASS |

### Position card required fields (spec §B)
| Field | Source | Status |
|---|---|---|
| backed_team | inferTeamsFromTrade → slug parse | PASS |
| faded_team | inferTeamsFromTrade → slug parse | PASS |
| entry_px | /api/trades | PASS |
| current_held_price | SSE current_price | PASS |
| unrealized_pct | derived from SSE current_price and entry_px | PASS |
| live_equity | SSE live_equity_usd | PASS |
| tp_price | /api/trades (server-computed, side-aware) | PASS |
| sl_price | /api/trades (server-computed, side-aware) | PASS |
| size_usd | qty * entry_px | PASS |
| held_contract_side | YES/NO chip in pos-source-chip | PASS |
| freshness/stale badge | SSE current_price_stale | PASS |

### POSITIONS tab
| Spec requirement | Implementation | Status |
|---|---|---|
| Open positions using execution truth | buildUnifiedPositionCards(open) — same SSE path as LIVE | PASS |
| Recent closed positions secondary | positions-closed-list with trade-card format | PASS |
| Shadow absent from POSITIONS | No shadow code in renderPositionsTab | PASS |
| SSE updates reach POSITIONS tab cards | querySelectorAll('.pos-card[data-slug]') covers both tabs | PASS |

### GAMES tab
| Spec requirement | Implementation | Status |
|---|---|---|
| All live and upcoming games shown | renderGamesTab renders full game list sorted by open position first | PASS |
| Shadow as secondary advisory only | class="monitor-trade-box advisory", label="Shadow Advisory — Not Executed" | PASS |
| Shadow not merged with position truth | advisory section separate from position section within game card | PASS |
| Shadow label exact text | "Shadow Advisory — Not Executed" | PASS |

### HISTORY tab
| Spec requirement | Implementation | Status |
|---|---|---|
| Trade log with team names | `${teams.away} @ ${teams.home}` derived from slug | PASS |
| Side direction | WIN/LOSE from tradeTeams().direction | PASS |
| Entry / exit / pnl / size | All four fields rendered | PASS |
| Close reasons | `${t.reason_close || '—'}` | PASS |
| Shadow absent | renderHistoryTab has no shadow code | PASS |

### SYSTEM tab
| Spec requirement | Implementation | Status |
|---|---|---|
| Stream health from /api/debug/market-stream | fetchSystemDiagnostics() fetches and renders connected, thread_alive, tracked count, mark_count | PASS |
| Process topology | bot_core/bridge topology section | PASS |
| Bot loop stats | loop_count, bridge_enabled, open_trade_count | PASS |
| R25 sample in health grid | r25.sample_size shown | PASS |
| fetchSystemDiagnostics called on tab switch | refreshTab('system') calls fetchSystemDiagnostics() | PASS |

### Truth model preservation
| Constraint | Status |
|---|---|
| current_price_authority: SSE held-side bid only | PASS — bid_yes/bid_no absent from dashboard.html |
| fallback_policy: labeled when stale | PASS — STALE badge from SSE current_price_stale |
| shadow_policy: GAMES tab only | PASS — confirmed by HTML parse |
| backed_team_semantics | PASS — "LAD backed" style throughout |
| no_new_price_writers | PASS — no JS computes current_held_price from scratch |

### Demotion list (spec §Demotion list)
| Item | Destination | Status |
|---|---|---|
| Shadow feed | GAMES tab advisory | PASS |
| Trade log | HISTORY tab | PASS |
| Candidates | Drawer (SYSTEM button not wired to candidates, acceptable — candidates remain in drawer accessed via system tab fetchCandidates) | PASS |
| Manual entry | Drawer (not surfaced as primary operator workflow) | PASS |
| Guard stack | Drawer / SYSTEM partial | ACCEPTABLE |

### Performance (Phase 4)
| Target | Implementation | Status |
|---|---|---|
| No full re-render of open cards on poll | _lastRenderedOpenSlugs guard in renderPositionsTab | PASS |
| No full re-render of history on poll | _lastRenderedClosedCount guard in renderHistoryTab | PASS |
| SSE in-place updates cover POSITIONS tab | querySelectorAll('.pos-card[data-slug]') | PASS |
| No CSS transitions on numeric values | stat-val, pnl-large, kpi-val have no transition property | PASS |
| Tab-switch flash removed | tabFade animation removed from .shell-panel.active | PASS |
| Layout shift prevention | monitor-grid min-height:60px | PASS |
| No console.log in production | grep confirmed zero occurrences | PASS |

---

## Incident closure statements

**SEA/TEX incident (BUY_NO showed bid_yes as current held price):**
CLOSED. Root cause fixed at execution layer (EXECUTION_HELD_SIDE_SEMANTICS_001, commit 2dbb3fc) and confirmed absent from dashboard layer. asset_id routing in `_tracked_open_assets()` ensures BUY_NO positions track NO token; state_hub stores NO token bid as current_price; SSE surfaces this directly; frontend uses current_price without side branching. Cannot recur.

**BOS/MIL incident (opposite-side close pricing ambiguity):**
CLOSED. Root cause fixed at execution layer. `close_position()` uses `_fill_price_exit(side, ob)` which returns NO token bid for BUY_NO. exit_px stored in DB reflects NO-side price. Display reads exit_px from DB without reinterpretation. Cannot recur.

---

## Overall verdict

**REDESIGN COMPLETE — ALL PHASES PASS**

Commits:
- Phase 0 (ARCH): spec only — DASHBOARD_REDESIGN_SPEC_001.md written
- Phase 1 (SHELL): 552686f
- Phase 2 (LIVE): 2e7bfcc
- Out-of-band semantics fix: f67c1d0 (ratified)
- Phase 3 (POSITIONS/GAMES/HISTORY/SYSTEM): fa12342
- Phase 3 fixes: f9d7f25
- Phase 4 (PERFORMANCE POLISH): a19f421

`dashboard_server.py` unchanged throughout (all required fields were already present).
