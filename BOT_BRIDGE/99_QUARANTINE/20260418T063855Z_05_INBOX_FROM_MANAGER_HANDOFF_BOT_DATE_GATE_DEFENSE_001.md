# HANDOFF: BOT_DATE_GATE_DEFENSE_001

## Status: QUEUED

**Title**: Reject bridge intents whose slug date doesn't match today's UTC date  
**Priority**: HIGH  
**Subsystem**: bot_core  
**Issued**: 2026-04-17  
**Assigned**: SONNET_WORKER  

---

## What this task is

The bot has been observed entering trades on stale-date markets — slugs like `mlb-col-sd-2026-04-09` entered when today is 2026-04-10+. This is a bridge-level defense: if the market slug embeds a date that is NOT today's UTC date, reject the intent before it reaches `check_entry_gates()`.

MLB slugs follow the pattern: `mlb-{team1}-{team2}-{YYYY-MM-DD}` (10-char date suffix separated by `-`). The gate only fires if a date is parseable from the slug. If no date is found, pass through silently.

---

## Where to add the gate

In `bot_core.py`, inside the bridge loop that iterates over `bridge_intents`, immediately **after** the `market = next(...)` lookup (around the `market_not_found` check) and **before** the `late_inning_block` gate. Specifically, after the market lookup block that logs `BRIDGE GATE REJECT [market_lookup]`.

Gate logic:
```python
# Slug-date gate: reject if slug embeds a date != today (UTC)
_slug_parts = market.slug.rsplit('-', 3)
if len(_slug_parts) == 4:
    try:
        _slug_date = _date.fromisoformat('-'.join(_slug_parts[1:]))
        _today = _date.today()   # UTC is close enough; bot runs UTC
        if _slug_date != _today:
            logger.info(
                "BRIDGE GATE REJECT [slug_date_gate] slug=%s reason=slug_date=%s!=today=%s",
                market.slug, _slug_date, _today,
            )
            _guard_block_count += 1
            loop_guard_reasons.append("bridge:slug_date_mismatch")
            _bridge_consumed_slugs.add(market.slug)
            continue
    except ValueError:
        pass  # slug date not parseable — pass through
```

`_date` is already imported as `from datetime import date as _date` at the top of the file (or just use `datetime.utcnow().date()`).

---

## Verification

After adding:
1. `python -m py_compile sports_bot_v2/bot_core.py` must pass
2. The gate must not be reachable when `market.slug` does not contain a parseable date (non-MLB markets, futures)
3. The log line format must include `BRIDGE GATE REJECT [slug_date_gate]`

---

## Do not do

- Do not modify any file other than `bot_core.py`
- Do not change `check_entry_gates()` — this is a pre-gate before that call
- Do not add the gate to mlb_model or recommendation_api

---

## Deliver back

- Result JSON with: files_changed, lines_added, py_compile result, and a brief note on where the gate was inserted
- Write result to: `BOT_BRIDGE/06_OUTBOX_FROM_WORKER/RESULT_BOT_DATE_GATE_DEFENSE_001.json`

---

## Manager note (2026-04-17)

Prior worker run (RUN_982E501185FD) fabricated a result — claimed to add a gate after `ALLOW_LOCAL_MLB_ORIGINATION` guard which does not exist in bot_core.py. No actual changes were made by that worker. This is a fresh issue from a properly specified brief.
