# Skill: Mobile Dashboard Designer

Rules for this dashboard's mobile layout.

## Core principles
- Design for 375px width first, then expand to 800px+ desktop
- Max content width 420px in left column; right column fills remaining space
- On mobile: `app-body` is flex-column, left col on top, right col below
- On desktop (≥800px): `app-body` is 2-col grid (420px | 1fr)

## Touch targets
- All tappable elements: min-height 44px, min-width 44px
- Buttons use `width:100%` on mobile
- Tab buttons: height 44px, flex-shrink:0 (no wrapping)

## No horizontal overflow
- Tables are replaced with cards
- Tabs use `overflow-x:auto; scrollbar-width:none`
- Long strings use `overflow:hidden; text-overflow:ellipsis; white-space:nowrap`
- Never use `min-width` on anything inside a flex container without `overflow:hidden`

## Typography scale (mobile)
- HUD values: 13-15px font-weight 800
- Card titles: 20px font-weight 900
- Stat values: 15-16px font-weight 800
- Meta / labels: 8-10px monospace uppercase
- Body: 12-14px

## Card hierarchy
1. Active Position cards — most prominent (colored top border, glow on resolve)
2. Game cards — medium prominence (border-radius: 12px)
3. Shadow feed / trade cards — compact (border-radius: 8px)
4. KPI strip — grid, always visible above drawer

## Dark theme palette
- Background layers: #080c12 → #0d1520 → #111c2e → #172035
- Borders: #1e2d3d (normal), #253245 (emphasis)
- Accent: green #00d09e, red #ff4d6d, gold #fbbf24, blue #38bdf8, purple #a78bfa
- Text: #e2e8f0 (primary), #94a3b8 (secondary), #475569 (muted), #2a3547 (very dim)
