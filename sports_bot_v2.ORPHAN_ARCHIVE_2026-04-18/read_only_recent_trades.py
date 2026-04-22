import sqlite3

path = r"C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db"
conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
cur = conn.cursor()
rows = cur.execute(
    "SELECT id, ts_open, market_slug, side, qty, entry_px, reason_open, source FROM trades ORDER BY id DESC LIMIT 5"
).fetchall()
for row in rows:
    print(row)
conn.close()
