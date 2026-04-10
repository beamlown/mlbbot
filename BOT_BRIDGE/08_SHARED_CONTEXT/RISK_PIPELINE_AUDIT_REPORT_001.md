# RISK_PIPELINE_AUDIT_REPORT_001

Status: **VERIFIED/PARTIAL** (read-only audit completed)
Scope repo audited: `C:\Users\johnny\Desktop\sports_bot_v2`

## Preflight
- `core/risk.py` readable/importable without runtime side effects beyond env constant load: **VERIFIED** (`python -c "import core.risk"` succeeded).
- `core/paper_exec.py` readable: **VERIFIED**.
- `bot_core.py` compile check: **VERIFIED** (`python -m py_compile bot_core.py` succeeded).
- `.env` present/readable: **VERIFIED** (`.env:1-115`).
- `core/types.py` imports resolvable: **VERIFIED** (`python -c "import core.types"` succeeded).

---

## 1) Entry pipeline map (ordered gates)
### Runtime order in `bot_core.py`
1. Skip inactive/closed markets (`bot_core.py:336`) and `market_type == "other"` (`bot_core.py:338`).
2. Fetch OB, then microstructure gate `if not ob.micro_ok: continue` (`bot_core.py:357`).
3. Local-origination gate `if not ALLOW_LOCAL_MLB_ORIGINATION: continue` (`bot_core.py:363`, env source at `bot_core.py:106`).
4. Date gate `_slug_date != _date.today(): continue` (`bot_core.py:376`).
5. Risk waterfall call `check_entry_gates(...)` (`bot_core.py:389-396`).
6. On pass: open simulated trade via `open_position`, persist via `insert_open_trade` (`bot_core.py:462`).

### Waterfall gates inside `check_entry_gates` (exact order)
- Market type enable flags (totals/spreads/moneylines) (`core/risk.py:107-114`)
- Spread cap (`core/risk.py:116-117`)
- Max entry price (`core/risk.py:119-122`)
- Near-resolution entry block (`core/risk.py:125-128`)
- Min depth (`core/risk.py:130-132`)
- Imbalance cap (`core/risk.py:134-135`)
- Min confidence (`core/risk.py:137-138`)
- Signal must not be NONE (`core/risk.py:140-141`)
- Max concurrent (`core/risk.py:143-144`)
- Max per market (`core/risk.py:146-148`)
- SL cluster cooldown (`core/risk.py:150-152`)
- Too close to end (`core/risk.py:154-155`)
- Market cooldown map check (`core/risk.py:157-159`)
- Market validity (`resolved/closed/active/time/metadata/age`) (`core/risk.py:161-164`, `66-83`)

## 2) Sizing formula (verbatim)
From `core/paper_exec.py`:
- Confidence tiering and cap:
  - `if confidence >= CONF_TIER_VHIGH: mult = CONF_SIZE_HIGH_MULT` (`33-34`)
  - `elif confidence >= CONF_TIER_HIGH: mult = CONF_SIZE_MID_MULT` (`35-36`)
  - `sized = base_usd * mult` (`38`)
  - `return max(0.0, min(sized, MAX_POSITION_SIZE_USD))` (`39`)
- Open sizing path:
  - `recommended_size_usd = signal.components.get("recommended_size_dollars")` (`72`)
  - `size_usd = max(0.0, min(float(recommended_size_usd), MAX_POSITION_SIZE_USD))` (`75`)
  - fallback `size_usd = _confidence_size(PAPER_POSITION_SIZE_USD, signal.confidence)` (`77`, `79`)
  - `qty = size_usd / fill_px if fill_px > 0 else 0.0` (`80`)

Inputs used: confidence, base position size, optional recommended size, max position cap. **No bankroll-aware or session-loss-aware sizing input found.**

## 3) TP/SL exit map (every trigger + math)
From `core/risk.py:169-215`:
- `gap_stop`: `gap_threshold = AUTO_STOP_LOSS_PCT * 2.0`; trigger `held_unrealized_pct < -gap_threshold` (`183-186`)
- `near_resolution`: trigger `current_held_price >= NEAR_RESOLUTION_PRICE` (`188-190`)
- `take_profit`: trigger `held_unrealized_pct >= AUTO_TAKE_PROFIT_PCT` (`192-194`)
- `trailing_stop`: after peak tracking (`196-205`), when `new_peak >= TRAILING_STOP_ACTIVATE_PCT` and `drawdown_from_peak >= TRAILING_STOP_DRAWDOWN_PCT` (`201-205`)
- `stop_loss`: trigger `held_unrealized_pct <= -AUTO_STOP_LOSS_PCT` (`207-210`)
- `time_exit`: trigger `time_to_end_seconds < TIME_EXIT_BUFFER_SECONDS` (`212-213`)

### Env thresholds live values
- `AUTO_TAKE_PROFIT_PCT=0.40` (`.env:45`)
- `AUTO_STOP_LOSS_PCT=0.12` (`.env:46`)
- `NEAR_RESOLUTION_PRICE=0.97` (`.env:47`)
- `TRAILING_STOP_ACTIVATE_PCT=0.10` (`.env:48`)
- `TRAILING_STOP_DRAWDOWN_PCT=0.12` (`.env:49`)
- `TIME_EXIT_BUFFER_SECONDS=300` (`.env:50`)

### Exit cooldowns set in bot loop
- near_resolution: `+600s` (`bot_core.py:613-615`)
- stop_loss: `+1800s` (`bot_core.py:617-618`)
- gap_stop: `+3600s` (`bot_core.py:620`)
- checked at entry via `market_cooldown` in risk waterfall (`core/risk.py:157-159`)

### Exit persistence/logging integrity
- Standard close path (`should_close`) logs `CLOSE...` and persists close payload including `reason_close` from `close_position` (`bot_core.py:608-616`, `core/paper_exec.py:151`, `core/db.py:130-132`).
- **Resolved-market force-close path** persists `exit_px/pnl/fees` but does **not** pass `reason_close` or `ts_close` in `close_trade` payload (`bot_core.py:570-577`), so DB writes `reason_close=NULL`/`ts_close=NULL` via `close_data.get(...)` (`core/db.py:131-139`). It still logs a CLOSE line (`bot_core.py:581`).

## 4) Held-side pricing map
### Definition
- `def _held_bid(side, ob): return ob.bid_yes if side == "BUY_YES" else ob.bid_no` (`core/risk.py:46-47`; mirrored in `core/paper_exec.py:60-61`).

### Runtime derivation/callsites
- Exit checks derive held mark via `_held_bid` (`core/risk.py:177-181`).
- MTM in risk uses `_held_bid` (`core/risk.py:221-224`).
- Paper MTM uses `_held_bid` then slippage-adjusted held exit sim (`core/paper_exec.py:159-163`).

### Raw YES/NO bid usage instead of helper
- Entry near-resolution guard directly uses side-specific `ob.bid_yes`/`ob.bid_no` (`core/risk.py:125-128`) but logic remains held-side equivalent.
- Exit fill path uses `_fill_price_exit(side, ob)` with side-specific bid selection (`core/paper_exec.py:51-57`) and remains held-side equivalent.

### `_held_bid() is None` behavior
- `check_exit`: immediate no-exit (`return False, ""`) (`core/risk.py:178-179`).
- `mark_to_market` in risk: returns `0.0` (`core/risk.py:221-223`).
- `mark_to_market_value` in paper_exec: returns `0.0` (`core/paper_exec.py:159-160`).

## 5) Bankroll/session accounting map
- Realized canonical source: DB sum closed PnL (`core/db.py:200-204`).
- Bot state uses: `realized = total_realized_pnl()`, computes unrealized via MTM per open trade, net=`realized+unrealized` (`bot_core.py:138-181`).
- Dashboard bankroll in `/api/state`:
  - `net_pnl` from state realized (`dashboard_server.py:512`)
  - `current = STARTING_BANKROLL + net_pnl` (`513`)
  - `capital_committed` from open trades sum(entry_px*qty) (`305-319`)
  - `available_cash = current - capital_committed` (`520`)
- `/api/bankroll` endpoint uses only last 30 grouped days (`_daily_pnl_history`) and `net=sum(history)` (`237-244`, `904-907`), which is not guaranteed lifetime cumulative.

Definitions observed:
- lifetime_bankroll: **not explicit variable name**; closest is `STARTING_BANKROLL + total_realized_pnl` in state path (`dashboard_server.py:50`, `512-517`; `core/db.py:200-204`).
- session_baseline/session_pnl: **not explicitly implemented**.
- available_cash: `current - capital_committed` in `/api/state` (`dashboard_server.py:520`).
- capital_committed: sum of open `entry_px * qty` (`dashboard_server.py:305-319`).
- live_equity_total: from stream marks, sum `qty * current_price` (`dashboard_server.py:467-479`).

Double-counting check: no explicit double-add path found in `/api/state` path; `/api/bankroll` is separate alternate view.

## 6) Concurrency and cap map
- Global cap env/source: `MAX_CONCURRENT_TRADES` (`bot_core.py:30`, `.env:41`), enforced in risk waterfall (`core/risk.py:143-144`) and bridge pre-checks (`bot_core.py:481-494`).
- Per-market cap env/source: `MAX_TRADES_PER_MARKET` (`bot_core.py:31`, `.env:42`), enforced in risk waterfall (`core/risk.py:146-148`).
- DB also enforces one open per slug via unique partial index (`core/db.py:80-82`).
- Per-session max loss cap: **not found**.
- Daily max loss cap: **not found**.

---

## Gaps table
| surface | gap description | severity |
|---|---|---|
| TP/SL persistence | `market_resolved` close path omits `reason_close` and `ts_close` in payload (`bot_core.py:570-577`), DB writes NULLs (`core/db.py:131-139`) | HIGH |
| Sizing | No bankroll-aware sizing input (size ignores current bankroll/drawdown/session loss) (`core/paper_exec.py:72-80`) | HIGH |
| Session risk controls | No per-session max loss cap, no daily max loss cap found in risk/loop | HIGH |
| Accounting surface consistency | `/api/bankroll` computes net from 30-day grouped history, not canonical lifetime sum (`dashboard_server.py:237-244`, `904-907`) | MED |
| Session accounting definitions | `session_baseline` / `session_pnl` not explicit in code | MED |

## Broken invariants table
| location | invariant | what actually happens |
|---|---|---|
| `bot_core.py:570-577` + `core/db.py:131-139` | Every close should persist `exit_px` and `reason_close` | `market_resolved` closes persist `exit_px` but `reason_close` (and `ts_close`) are NULL |

---

## Recommended phase priorities
1. **Phase 1 (critical):** Fix close-data integrity on `market_resolved` path (always write `reason_close`, `ts_close`).
2. **Phase 2 (risk containment):** Add hard session/daily max-loss kill switches before new entries.
3. **Phase 3 (sizing hardening):** Add bankroll/drawdown-aware size constraints.
4. **Phase 4 (reporting consistency):** Align `/api/bankroll` with canonical lifetime realized PnL query.

---

## Acceptance evidence
- Report exists at this path.
- All six audit surfaces covered with file:line citations.
- Thresholds include env var names and current values.
- No production edits performed (`git diff --name-only` in repo: empty).
