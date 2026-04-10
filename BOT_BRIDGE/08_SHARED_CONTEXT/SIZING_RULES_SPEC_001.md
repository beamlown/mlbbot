# SIZING_RULES_SPEC_001 — Per-Trade Position Sizing Rules
**Generated: 2026-04-10**
**Source files: core/paper_exec.py, core/risk.py**
**Env values as of 2026-04-10**

---

## 1. Canonical Sizing Formula

```
size_usd = clamp(base_usd * tier_mult, 0, MAX_POSITION_SIZE_USD)
qty       = size_usd / fill_px
```

Where:
- `base_usd` = `PAPER_POSITION_SIZE_USD` (default $50, env-configurable)
- `tier_mult` = confidence tier multiplier (see §2)
- `MAX_POSITION_SIZE_USD` = absolute per-trade cap ($100, env-configurable)
- `fill_px` = `ask_side * (1 + PAPER_SLIPPAGE_PCT)` where ask_side is ask_yes (BUY_YES) or ask_no (BUY_NO), clamped [0.01, 0.99]

**Override path:** If `signal.components["recommended_size_dollars"]` is present (model bridge field), `size_usd = clamp(recommended_size_dollars, 0, MAX_POSITION_SIZE_USD)`. The confidence tier formula is bypassed, but the cap is always enforced.

---

## 2. Confidence Tier Table

| Condition | Tier | Multiplier | Effective size (base=$50) |
|-----------|------|-----------|---------------------------|
| conf < 0.70 | Base | 1.00× | $50.00 |
| 0.70 ≤ conf < 0.80 | High | 1.25× | $62.50 |
| conf ≥ 0.80 | Very High | 1.50× | $75.00 |
| Any tier | Cap | — | max $100.00 |

Env vars: `CONF_TIER_HIGH=0.70`, `CONF_TIER_VHIGH=0.80`, `CONF_SIZE_MID_MULT=1.25`, `CONF_SIZE_HIGH_MULT=1.50`
Gate: `CONF_SIZING_ENABLED=true` — if false, `tier_mult` = 1.0 always.

---

## 3. Size Caps

| Rule | Cap | Env var | Live value | Code location |
|------|-----|---------|-----------|---------------|
| Per-trade max | $100 | `MAX_POSITION_SIZE_USD` | 100 | `paper_exec.py:24,40,76` |
| Concurrent trades (count) | 3 | `MAX_CONCURRENT_TRADES` | 3 | `risk.py:27,201` |
| Per-market concurrent | 1 | `MAX_TRADES_PER_MARKET` | 1 | `risk.py:28,205` |
| **Per-session USD cap** | **NONE** | *(missing)* | — | **GAP — see §6** |

---

## 4. Liquidity Gate

**Gate type:** Hard block (all-or-nothing before entry).

```python
# risk.py:188-190
depth = min(ob.depth_top5_usd_yes, ob.depth_top5_usd_no)
if depth < eff_min_depth:
    return False, [f"depth_too_low:{depth:.1f}<{eff_min_depth:.1f}"]
```

Env vars: `MIN_TOUCH_DEPTH_USD=200` (takes precedence over `MIN_DEPTH_TOP5_USD=500` since explicitly set).

**Safety property:** Since `MIN_TOUCH_DEPTH_USD=200 > MAX_POSITION_SIZE_USD=100`, any trade that passes the depth gate always has sufficient depth to absorb the full position size. Size cannot exceed available depth.

---

## 5. Worked Example

**Given:** confidence=0.65, bankroll=$900, 1 open position, depth=$200

1. Depth gate: min(depth_yes, depth_no) ≥ $200 ✓ (assume depth=$200 passes exactly)
2. Concurrent gate: open_count=1 < MAX_CONCURRENT_TRADES=3 ✓
3. Confidence=0.65 < CONF_TIER_HIGH=0.70 → tier_mult=1.0
4. base_usd = PAPER_POSITION_SIZE_USD = $50.00
5. size_usd = $50.00 × 1.0 = $50.00 → clamp($50, 0, $100) = **$50.00**
6. fill_px = ask_side × 1.005 (slippage) — assume ask_yes=0.50 → fill_px=0.5025
7. qty = $50.00 / 0.5025 = **99.50 contracts**
8. committed_usd = qty × entry_px = 99.50 × 0.5025 = **$50.00** ✓
9. **Bankroll ($900) is NOT factored into sizing** — this is a documented gap (§6)

**Result: 99.50 contracts at $0.5025, $50.00 committed.**

---

## 6. Gaps and Findings

### GAP-1: No per-session total USD commitment cap (HIGH)
- **Rule:** SIZE_BOUNDED_PER_SESSION
- **Current state:** Only a count cap (`MAX_CONCURRENT_TRADES=3`). Maximum theoretical exposure = 3 × $100 = $300, with no dollar-denominated ceiling.
- **Bankroll relationship:** `PAPER_POSITION_SIZE_USD` is a fixed dollar amount — it does not scale with bankroll balance or drawdown. A $900 bankroll and a $200 bankroll receive the same $50 base size.
- **Deferred to:** BANKROLL_SESSION_RULES_001 — will add `MAX_TOTAL_COMMITTED_USD` cap and bankroll-aware scaling.
- **Severity:** HIGH (matches phase 0 audit finding)

### GAP-2: Bankroll not factored into sizing (HIGH)
- **Rule:** SIZE_EXPLAINABLE
- **Current state:** Sizing formula ignores bankroll. A drawdown to 10% of starting capital would still allow full-size entries.
- **Deferred to:** BANKROLL_SESSION_RULES_001
- **Severity:** HIGH (matches phase 0 audit finding: "Sizing not bankroll/drawdown-aware")

---

## 7. Invariant Status Summary

| Rule | Status | Evidence |
|------|--------|----------|
| SIZE_BOUNDED_PER_TRADE | ✓ CONFIRMED | `paper_exec.py:40,76` — `min(sized, MAX_POSITION_SIZE_USD)` |
| SIZE_BOUNDED_PER_SESSION | ✗ GAP | Count cap only. USD cap missing. → BANKROLL_SESSION_RULES_001 |
| SIZE_PROPORTIONAL_TO_CONFIDENCE | ✓ CONFIRMED | `paper_exec.py:27-40` — tier table enforced |
| SIZE_RESPECTS_LIQUIDITY | ✓ CONFIRMED | `risk.py:188-190` depth gate precedes entry; min_depth > max_size |
| SIZE_EXPLAINABLE | ⚠ PARTIAL | Formula documented. Bankroll-agnostic by design for now. → GAP-2 |
| QTY_CONSISTENT_WITH_COMMITTED_USD | ✓ CONFIRMED | `paper_exec.py:81` — `qty = size_usd / fill_px` ∴ qty × fill_px = size_usd exactly |
