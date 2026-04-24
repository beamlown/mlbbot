# REVIEW_TP_SL_SCHEMA_NORMALIZATION_001

Decision: APPROVED
Date: 2026-04-10

## Scope / guardrails check
- Only in-scope files were changed:
  - `sports_bot_v2/core/risk.py`
  - `sports_bot_v2/core/paper_exec.py`
- Out-of-scope files (`bot_core.py`, `dashboard_server.py`, etc.) were not modified.
- No TP/SL threshold constants were changed.

## Preflight dependency check
- `RISK_PIPELINE_AUDIT_001` review file shows **Decision: APPROVED**.
- Audit report read before implementation: `BOT_BRIDGE/08_SHARED_CONTEXT/RISK_PIPELINE_AUDIT_REPORT_001.md`.

## Implemented normalization

### 1) Canonical TP/SL + risk math helpers in `core/risk.py`
Added full helper implementations:

```python
def get_committed_usd(trade: Trade) -> float:
    entry_px = trade.entry_px or 0.0
    qty = trade.qty or 0.0
    return entry_px * qty


def get_tp_price(trade: Trade) -> float:
    entry_px = trade.entry_px or 0.0
    return entry_px * (1.0 + AUTO_TAKE_PROFIT_PCT)


def get_sl_price(trade: Trade) -> float:
    entry_px = trade.entry_px or 0.0
    return entry_px * (1.0 - AUTO_STOP_LOSS_PCT)


def get_max_loss_usd(trade: Trade) -> float:
    return (get_sl_price(trade) - (trade.entry_px or 0.0)) * (trade.qty or 0.0)


def parse_backed_faded_teams(market_slug: str, side: str) -> tuple[str | None, str | None]:
    m = re.match(r"^[A-Za-z0-9_]+-([A-Za-z0-9_]+)-([A-Za-z0-9_]+)-\d{4}-\d{2}-\d{2}$", market_slug)
    if not m:
        return None, None
    team_yes = m.group(1).upper()
    team_no = m.group(2).upper()
    if side == "BUY_YES":
        return team_yes, team_no
    return team_no, team_yes


def get_current_held_price(trade: Trade, ob: OBSnapshot) -> float | None:
    return _held_bid(trade.side, ob)


def get_held_token_id(trade: Trade, market: Market | None = None) -> str | None:
    if market is None:
        return None
    return market.yes_token_id if trade.side == "BUY_YES" else market.no_token_id


def get_risk_packet(trade: Trade, ob: OBSnapshot | None = None, market: Market | None = None) -> dict[str, Any]:
    backed_team, faded_team = parse_backed_faded_teams(trade.market_slug, trade.side)
    return {
        "entry_px": trade.entry_px,
        "qty": trade.qty,
        "committed_usd": get_committed_usd(trade),
        "tp_price": get_tp_price(trade),
        "sl_price": get_sl_price(trade),
        "max_loss_usd": get_max_loss_usd(trade),
        "held_token_id": get_held_token_id(trade, market),
        "backed_team": backed_team,
        "faded_team": faded_team,
        "current_held_price": get_current_held_price(trade, ob) if ob is not None else None,
    }
```

### 2) Exit logic now consumes canonical TP/SL helpers
Before (scattered inline pct checks):
```python
if held_unrealized_pct >= AUTO_TAKE_PROFIT_PCT:
...
if held_unrealized_pct <= -AUTO_STOP_LOSS_PCT:
```
After (canonical function outputs):
```python
tp_price = get_tp_price(trade)
sl_price = get_sl_price(trade)
...
if current_held_price >= tp_price:
...
if current_held_price <= sl_price:
```

### 3) `open_position()` now logs canonical risk packet
Before:
- `reason_open` used `signal.components['tp_price']` / `['sl_price']` (potentially non-canonical).

After:
- `open_position()` builds `Trade` first, then calls:
  - `risk_packet = get_risk_packet(trade, ob=ob, market=market)`
- `reason_open` now logs `risk={...}` with canonical fields including held token id, backed/faded teams, committed USD, max loss, and current held price.

## Verification
- `python -m py_compile core/risk.py core/paper_exec.py core/types.py` → passed
- `git diff --name-only` output:
  - `sports_bot_v2/core/paper_exec.py`
  - `sports_bot_v2/core/risk.py`
- Allowed-files check for this task: pass

## Notes
- Trade dataclass was not expanded (schema bloat avoided).
- Held-side pricing remains based on `_held_bid()`; no YES/NO proxy substitution was introduced.
