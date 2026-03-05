import sqlite3

conn = sqlite3.connect('instance/tenders.db')
c = conn.cursor()

print("=== Database Analysis ===")

# Total count
c.execute('SELECT COUNT(*) FROM tenders')
total = c.fetchone()[0]
print(f'Total tenders: {total}')

# State distribution
c.execute('SELECT state, COUNT(*) FROM tenders GROUP BY state')
print('\nBy State:')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Check for duplicates
c.execute('SELECT COUNT(*) FROM (SELECT source_url FROM tenders GROUP BY source_url HAVING COUNT(*) > 1)')
dup_count = c.fetchone()[0]
print(f'\nDuplicate source_urls: {dup_count}')

# Empty titles
c.execute('SELECT COUNT(*) FROM tenders WHERE title IS NULL OR title = ""')
print(f'Empty/NULL titles: {c.fetchone()[0]}')

# Unknown state
c.execute('SELECT COUNT(*) FROM tenders WHERE state = "Unknown"')
print(f'Unknown state: {c.fetchone()[0]}')

# Sample records
print('\nSample records:')
c.execute('SELECT id, title, state, issuing_authority, source_url FROM tenders LIMIT 3')
for row in c.fetchall():
    print(f'ID:{row[0]} State:{row[2]} Authority:{row[3]}')
    print(f'  Title: {str(row[1])[:80]}')
    print(f'  URL: {row[4][:60]}...')

conn.close()
