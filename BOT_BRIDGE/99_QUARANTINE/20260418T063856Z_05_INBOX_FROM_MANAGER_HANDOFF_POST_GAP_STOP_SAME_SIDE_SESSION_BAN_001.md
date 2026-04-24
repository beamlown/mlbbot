# HANDOFF: POST_GAP_STOP_SAME_SIDE_SESSION_BAN_001

## What you are doing
Adding a session-level same-side ban to `bot_core.py`. After any `gap_stop` exit on a (slug, side) pair, block any new entry on that exact (slug, side) for the rest of the session.

## Why this exists
Tonight's gap stops totaled **-$499.99** across 21 trades. The existing 60-minute market cooldown does not distinguish direction — it allows same-side re-entry after the cooldown expires. CWS-KC BUY_YES was re-entered after every gap_stop, following the price from 0.39 down to 0.01. A gap_stop means the market moved 30–90% against the position in a single 30-second loop — the game outcome is being decided and the model is on the wrong side.

## The fix — exactly what to implement

**Step 1 — declare the ban set (module level in bot_core.py):**
```python
_session_gap_stop_bans: set = set()  # (slug, side) tuples
```

**Step 2 — populate on gap_stop exit (in the close/exit path):**
```python
if reason_close == "gap_stop":
    _session_gap_stop_bans.add((slug, side))
    logger.info("SESSION BAN set for (%s, %s) — gap_stop exit", slug, side)
```

**Step 3 — check at entry gate (before or inside check_entry_gates):**
```python
if (slug, side) in _session_gap_stop_bans:
    return False, [f"post_gap_stop_session_ban:{slug}:{side}"]
```

## Important design notes
- **Only blocks the SAME side** — BUY_YES gap_stop bans BUY_YES, not BUY_NO
- **In-memory only** — resets on restart, no DB/state.json changes needed
- **Does not replace the 60-min cooldown** — both apply independently
- **Do not touch risk.py** — this ban lives only in bot_core.py

## Constraints
- Only modify `bot_core.py`
- Do not touch risk.py, .env, dashboard, or exit threshold values
- py_compile must pass

## What you must verify
- Show where in the close path the ban is added
- Show where in the entry path it's checked
- Confirm risk.py was NOT touched
- Run py_compile
