# HANDOFF — DASH_003
## Replace full scoreboard with compact games ticker

---

## Context

The Live Games section renders large full-width game cards that push positions below the fold. Replace with a compact ticker row of score chips. DASH_002 must be complete before starting this (same file).

---

## File to change

`sports_bot_v2/dashboard.html` — ONLY this file.

---

## Change

### 1. Replace the games section HTML

**Find (around line 401):**
```html
<div class="section">
  <div class="section-header">
    <span class="section-title">Live Games</span>
    <span class="refresh-ts" id="games-refresh-ts">—</span>
  </div>
  <div id="games-list"><div class="empty-state">loading scoreboard…</div></div>
</div>
```

**Replace with:**
```html
<div id="games-ticker" style="display:flex;flex-wrap:wrap;gap:6px;padding:8px 14px;border-bottom:1px solid var(--border);min-height:32px;">
  <span class="dim" style="font-size:11px;font-family:var(--mono);">loading games…</span>
</div>
```

---

### 2. Update the games render function

Find the JS function that populates `#games-list` (likely `renderGames()` or similar). Replace its body so it builds chips into `#games-ticker` instead of cards into `#games-list`.

**New render logic:**
```javascript
function renderGames(games) {
  const el = document.getElementById('games-ticker');
  if (!el) return;
  if (!games || !games.length) {
    el.innerHTML = '<span class="dim" style="font-size:11px;font-family:var(--mono);">no games today</span>';
    return;
  }
  el.innerHTML = games.map(g => {
    const away = shortTeam(g.away_team || '');
    const home = shortTeam(g.home_team || '');
    const aScore = g.away_score ?? '–';
    const hScore = g.home_score ?? '–';
    const status = g.inning ? `i${g.inning}` : (g.status === 'final' || g.status === 'closed' ? 'F' : 'S');
    const live = !!g.inning;
    return `<span style="font-size:11px;font-family:var(--mono);padding:2px 8px;border-radius:4px;background:${live ? 'var(--green-dim)' : 'var(--bg3)'};color:${live ? 'var(--green)' : 'var(--text2)'};">${away} ${aScore} · ${home} ${hScore} <span class="dim">(${status})</span></span>`;
  }).join('');
}
```

---

## Verification

```
cd C:\Users\johnny\Desktop\sports_bot_v2
python dashboard_server.py
```

Open `http://localhost:8900`. Games should appear as a single compact line of chips, not full scoreboard cards.

## Rollback

Revert `dashboard.html` only.
