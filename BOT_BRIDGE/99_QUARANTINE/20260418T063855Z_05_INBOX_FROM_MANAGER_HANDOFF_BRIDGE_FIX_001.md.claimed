# HANDOFF — BRIDGE_FIX_001
## Add MAX_CONCURRENT_TRADES cap + per-open slug re-check to bridge section

---

## Context

On 2026-04-04 there was an incident: 6 concurrent bot_core.py processes each opened trades for the same game slugs (2–3× per game), causing -$218 in losses. Root cause: the bridge section in bot_core.py has NO concurrent trade cap. The native signal loop uses `check_entry_gates()` which enforces `MAX_CONCURRENT_TRADES`, but the bridge block (lines 439–471) skips that check entirely.

Bridge is currently DISABLED (`ENABLE_MODEL_BRIDGE = False`). This fix is a prerequisite for re-enabling it.

---

## File to change

`sports_bot_v2/bot_core.py` — ONLY this file.

---

## Exact section to replace

Find the comment `# ── Model bridge (paper only) ─────────────────────────────────────` around line 439. Replace the entire bridge try/except block with the version below.

**Current code (lines ~439–471):**
```python
# ── Model bridge (paper only) ─────────────────────────────────────
try:
    open_trades = fetch_open_trades()
    open_slugs = {t.market_slug for t in open_trades}
    bridge_intents = get_approved_intents(open_slugs)
    for intent in bridge_intents:
        market = next((m for m in _markets if m.slug == intent["slug"]), None)
        if market is None:
            logger.info("BRIDGE GATE REJECT [market_lookup] slug=%s reason=market_not_found", intent["slug"])
            continue
        ob = get_orderbook_snapshot(market)
        signal = Signal(
            side=intent["side"],
            confidence=float(intent.get("confidence") or 0.0),
            fair_value_estimate=float(intent.get("entry_px") or 0.5),
            components={"bridge": True, "edge": intent.get("edge")},
            reasons=["model_bridge"],
        )
        trade = open_position(
            market,
            signal,
            ob,
            mode=mode_ctx.mode,
            source="model_bridge",
        )
        trade_id = insert_open_trade(trade, sport=SPORT)
        trade.id = trade_id
        logger.info(
            "BRIDGE OPEN trade=%d %s %s @ %.4f source=%s",
            trade_id, market.slug[:30], trade.side, trade.entry_px, trade.source,
        )
except Exception as e:
    logger.warning("Model bridge error: %s", e)
```

**Replace with:**
```python
# ── Model bridge (paper only) ─────────────────────────────────────
try:
    _bridge_open_check = fetch_open_trades()
    if len(_bridge_open_check) >= MAX_CONCURRENT_TRADES:
        logger.info(
            "BRIDGE SKIP — at capacity (%d/%d)",
            len(_bridge_open_check), MAX_CONCURRENT_TRADES,
        )
    else:
        open_slugs = {t.market_slug for t in _bridge_open_check}
        bridge_intents = get_approved_intents(open_slugs)
        for intent in bridge_intents:
            # Re-fetch each time to catch concurrent writes from other processes
            current_open = fetch_open_trades()
            if len(current_open) >= MAX_CONCURRENT_TRADES:
                logger.info(
                    "BRIDGE CAP HIT — stopping at %d/%d",
                    len(current_open), MAX_CONCURRENT_TRADES,
                )
                break
            current_open_slugs = {t.market_slug for t in current_open}
            if intent["slug"] in current_open_slugs:
                logger.info(
                    "BRIDGE RACE SKIP slug=%s reason=slug_opened_by_concurrent_process",
                    intent["slug"],
                )
                continue
            market = next((m for m in _markets if m.slug == intent["slug"]), None)
            if market is None:
                logger.info("BRIDGE GATE REJECT [market_lookup] slug=%s reason=market_not_found", intent["slug"])
                continue
            ob = get_orderbook_snapshot(market)
            signal = Signal(
                side=intent["side"],
                confidence=float(intent.get("confidence") or 0.0),
                fair_value_estimate=float(intent.get("entry_px") or 0.5),
                components={"bridge": True, "edge": intent.get("edge")},
                reasons=["model_bridge"],
            )
            trade = open_position(
                market,
                signal,
                ob,
                mode=mode_ctx.mode,
                source="model_bridge",
            )
            trade_id = insert_open_trade(trade, sport=SPORT)
            trade.id = trade_id
            logger.info(
                "BRIDGE OPEN trade=%d %s %s @ %.4f source=%s",
                trade_id, market.slug[:30], trade.side, trade.entry_px, trade.source,
            )
except Exception as e:
    logger.warning("Model bridge error: %s", e)
```

---

## What changed and why

1. **Cap check before bridge**: if `open_count >= MAX_CONCURRENT_TRADES`, skip bridge entirely for this loop. Matches what `check_entry_gates` does for the native signal loop.
2. **Per-intent re-fetch**: call `fetch_open_trades()` again before each individual open. This catches the race condition where another process opened a position between the outer fetch and this point.
3. **Race skip log**: if the slug appears in the fresh fetch, log `BRIDGE RACE SKIP` instead of `BRIDGE GATE REJECT [open_position]` (which came from model_bridge.py's stale check).

---

## Verification

1. `python bot_core.py` — should start, log "BRIDGE DISABLED" (kill switch still False — do NOT change it)
2. Code-only check: confirm the cap check and re-fetch are present
3. No other files should be modified

## Rollback

Revert `bot_core.py` only.
