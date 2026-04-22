// dugout.js — SSE client, toast, notifications, sounds, P&L recomputation.
(function () {
  'use strict';

  function toast(title, body, ok) {
    const root = document.getElementById('toast-root');
    if (!root) return;
    const el = document.createElement('div');
    el.className = 'toast' + (ok === false ? ' err' : '');
    el.innerHTML =
      '<div class="title">' + title + '</div>' +
      (body ? '<div>' + body + '</div>' : '');
    root.appendChild(el);
    setTimeout(() => el.classList.add('show'), 10);
    setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, 4000);
  }

  function ensureNotifyPermission() {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
      document.addEventListener('click', () => {
        if (Notification.permission === 'default') Notification.requestPermission();
      }, { once: true });
    }
  }

  function notify(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
      try { new Notification(title, { body }); } catch (e) { /* ignore */ }
    }
  }

  const soundCache = {};
  function playSound(name) {
    try {
      if (!soundCache[name]) {
        soundCache[name] = new Audio('/static/sounds/' + name + '.wav');
        soundCache[name].volume = 0.5;
      }
      soundCache[name].currentTime = 0;
      soundCache[name].play().catch(() => {});
    } catch (e) { /* ignore */ }
  }

  let es = null;
  let reconnectAt = null;

  function setSSEChip(state) {
    const chip = document.getElementById('sse-chip');
    if (!chip) return;
    if (state === 'ok') { chip.className = 'chip-pixel chip-pixel--ok'; chip.textContent = '✓ LIVE'; }
    else if (state === 'stale') { chip.className = 'chip-pixel chip-pixel--warn chip-stale'; chip.textContent = '⚠ STALE'; }
  }

  function connectSSE() {
    if (es) { try { es.close(); } catch (e) {} }
    es = new EventSource('/api/events');

    es.addEventListener('hello', () => setSSEChip('ok'));
    es.addEventListener('trade_entered', (e) => onTradeEntered(JSON.parse(e.data)));
    es.addEventListener('trade_exited',  (e) => onTradeExited(JSON.parse(e.data)));
    es.addEventListener('mark_update',   (e) => onMarkUpdate(JSON.parse(e.data)));

    es.onerror = () => {
      setSSEChip('stale');
      try { es.close(); } catch (e) {}
      if (!reconnectAt) playSound('foul');
      reconnectAt = setTimeout(() => { reconnectAt = null; connectSSE(); }, 3000);
    };
  }

  function onTradeEntered(p) {
    const title = '⚾ BASE HIT — TRADE FILLED';
    const body = p.side + ' · ' + p.slug + ' @ ' + Number(p.entry_px).toFixed(4) + ' · $' + Number(p.size_usd).toFixed(2);
    toast(title, body, true);
    notify(title, body);
    playSound('base_hit');
    if (window.dugoutOnTradeEntered) window.dugoutOnTradeEntered(p);
  }

  function onTradeExited(p) {
    const winning = (p.net_pnl || 0) >= 0;
    const title = winning ? '🏆 WALK-OFF — TRADE CLOSED' : '❌ STRIKEOUT — TRADE CLOSED';
    const pnlStr = (p.net_pnl >= 0 ? '+$' : '-$') + Math.abs(p.net_pnl || 0).toFixed(2);
    const body = p.slug + ' · ' + p.reason + ' · ' + pnlStr;
    toast(title, body, winning);
    notify(title, body);
    playSound(winning ? 'walkoff' : 'strikeout');
    if (window.dugoutOnTradeExited) window.dugoutOnTradeExited(p);
  }

  function onMarkUpdate(p) {
    const safeSlug = cssEscape(p.slug);
    document.querySelectorAll('.ticker-cell[data-slug="' + safeSlug + '"]').forEach((cell) => {
      const prev = parseFloat(cell.getAttribute('data-mark'));
      const markEl = cell.querySelector('.ticker-mark');
      const dirEl = cell.querySelector('.ticker-dir');
      if (markEl) markEl.textContent = (p.mark * 100).toFixed(2) + '¢';
      cell.setAttribute('data-mark', p.mark);
      if (!Number.isNaN(prev) && dirEl) {
        if (p.mark > prev) { dirEl.textContent = ' ▲'; dirEl.className = 'ticker-dir up'; }
        else if (p.mark < prev) { dirEl.textContent = ' ▼'; dirEl.className = 'ticker-dir down'; }
      }
    });
    document.querySelectorAll('.trade-row[data-slug="' + safeSlug + '"]').forEach((row) => {
      const entry = parseFloat(row.getAttribute('data-entry')) || 0;
      const qty = parseFloat(row.getAttribute('data-qty')) || 0;
      const markCell = row.querySelector('.mark-cell');
      const pnlCell = row.querySelector('.pnl-cell');
      const pctCell = row.querySelector('.pnl-pct');
      if (markCell) markCell.textContent = p.mark.toFixed(4);
      const pnl = (p.mark - entry) * qty;
      if (pnlCell) {
        pnlCell.textContent = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(2);
        pnlCell.classList.toggle('pnl-up', pnl >= 0);
        pnlCell.classList.toggle('pnl-down', pnl < 0);
        pnlCell.classList.remove('flash-up', 'flash-down');
        void pnlCell.offsetWidth;
        pnlCell.classList.add(pnl >= 0 ? 'flash-up' : 'flash-down');
      }
      if (pctCell && entry > 0 && qty > 0) {
        const pct = (pnl / (entry * qty)) * 100;
        pctCell.textContent = pct.toFixed(1) + '%';
      }
    });
    if (window.dugoutOnMarkUpdate) window.dugoutOnMarkUpdate(p);
  }

  function cssEscape(s) {
    return String(s).replace(/["\\]/g, '\\$&');
  }

  ensureNotifyPermission();
  connectSSE();
})();
