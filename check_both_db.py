import sqlite3
import os

# Check both databases
dbs = [
    'instance/tenders.db',
    'tenders.db'
]

for db_path in dbs:
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = c.fetchall()
            print(f"\n{db_path}:")
            print(f"  Tables: {tables}")
            if ('tenders',) in tables:
                c.execute('SELECT COUNT(*) FROM tenders')
                count = c.fetchone()[0]
                print(f"  Tender count: {count}")
                c.execute('SELECT state, COUNT(*) FROM tenders GROUP BY state')
                print(f"  By state: {c.fetchall()}")
            conn.close()
        except Exception as e:
            print(f"  Error: {e}")
