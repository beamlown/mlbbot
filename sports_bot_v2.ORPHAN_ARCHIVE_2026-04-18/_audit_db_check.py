import json
import sqlite3

conn = sqlite3.connect('trades_sports.db')
cur = conn.cursor()
print('INDEXES')
for row in cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='trades'"):
    print(json.dumps(row))
print('OPEN_ROWS')
print(json.dumps(list(cur.execute("SELECT id, market_slug, side, entry_px, qty, status FROM trades WHERE status='open' ORDER BY id"))))
print('DUPES')
print(json.dumps(list(cur.execute("SELECT market_slug, COUNT(1) as c FROM trades WHERE status='open' GROUP BY market_slug HAVING COUNT(1)>1"))))
conn.close()
