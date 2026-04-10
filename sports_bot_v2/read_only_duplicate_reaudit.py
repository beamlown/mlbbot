import sqlite3

path = r"C:\Users\johnny\Desktop\sports_bot_v2\trades_sports.db"
conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
cur = conn.cursor()

print(f"DB_PATH={path}")
print("=== INDEXES ===")
for name, sql in cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='trades' ORDER BY name"):
    print(name)
    print(sql)

print("=== DUPLICATE_OPEN_ROWS ===")
dups = cur.execute(
    "SELECT market_slug, COUNT(*) as c FROM trades WHERE status='open' GROUP BY market_slug HAVING COUNT(*) > 1 ORDER BY c DESC, market_slug"
).fetchall()
if dups:
    for row in dups:
        print(row)
else:
    print("NONE")

print("=== OPEN_ROW_COUNT ===")
print(cur.execute("SELECT COUNT(*) FROM trades WHERE status='open'").fetchone()[0])

print("=== OPEN_ROWS ===")
for row in cur.execute("SELECT id, market_slug, side, status, ts_open, source FROM trades WHERE status='open' ORDER BY id"):
    print(row)

conn.close()
