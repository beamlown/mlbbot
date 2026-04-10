# HANDOFF — DASH_004
## Merge HUD + header into single command bar, add bridge badge

---

## Context

There are currently two sticky elements at the top: a `.hud` strip (System / Mode / Positions / Live P&L) and a `.header` bar (logo, sport badge, mode badge, bot dot, hamburger). They overlap in content and waste vertical space. Merge into one `.cmdbar`. DASH_003 must be complete before starting (same file).

---

## File to change

`sports_bot_v2/dashboard.html` — ONLY this file.

---

## Change

### 1. Replace .hud + .header HTML with a single .cmdbar

**Find and delete the entire .hud div (around line 347–365):**
```html
<div class="hud">
  <div class="hud-item">...</div>
  <div class="hud-item">...</div>
  <div class="hud-item">...</div>
  <div class="hud-item">...</div>
</div>
```

**Find and replace the entire .header div (around line 367–378) with:**
```html
<div class="cmdbar">
  <div style="display:flex;align-items:center;gap:8px;">
    <span class="header-logo">⚾ Sports Bot</span>
    <span class="header-sport">MLB</span>
    <span id="mode-display"></span>
  </div>
  <div style="display:flex;align-items:center;gap:8px;">
    <div class="dot" id="bot-dot"></div>
    <span id="bot-status-text" style="font-size:11px;color:var(--text3);font-family:var(--mono);">connecting…</span>
    <span class="refresh-ts" id="last-refresh"></span>
    <span id="bridge-badge"></span>
  </div>
  <div style="display:flex;align-items:center;gap:10px;font-size:11px;font-family:var(--mono);color:var(--text2);">
    <span>Open: <span id="hud-active" style="color:var(--blue);font-weight:700;">—</span></span>
    <span>P&L: <span id="hud-unrlzd" style="font-weight:700;">—</span></span>
    <span id="hud-loop" style="color:var(--text3);">loop —</span>
  </div>
  <button class="mob-menu-btn" onclick="toggleDrawer()" title="Details">≡</button>
</div>
```

### 2. Add .cmdbar CSS

In the `<style>` block, add:
```css
.cmdbar {
  background:var(--bg2); border-bottom:1px solid var(--border);
  display:flex; align-items:center; justify-content:space-between;
  padding:6px 14px; position:sticky; top:0; z-index:200; gap:12px;
  flex-wrap:wrap;
}
```

### 3. Update JS that populates the bridge badge

In the state refresh function (where bot-dot, mode-display etc. are updated), add:

```javascript
const bridgeBadge = document.getElementById('bridge-badge');
if (bridgeBadge) {
  const on = state.bridge_enabled === true;
  bridgeBadge.innerHTML = `<span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;font-family:var(--mono);background:${on ? 'var(--green-dim)' : 'var(--red-dim)'};color:${on ? 'var(--green)' : 'var(--red)'};">BRIDGE ${on ? 'ON' : 'OFF'}</span>`;
}
```

### 4. Update hud-loop

Where the loop count is set (currently may target `hud-loop` or similar), ensure it targets `id="hud-loop"` in the new cmdbar.

---

## Verification

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python dashboard_server.py
```

Open `http://localhost:8900`. Single bar at top — no separate HUD strip. Bridge badge visible. Hamburger opens drawer.

## Rollback

Revert `dashboard.html` only.
