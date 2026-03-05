import sqlite3

conn = sqlite3.connect('instance/tenders.db')
c = conn.cursor()

print("=== Cleaning Junk Data ===")

initial_count = c.execute('SELECT COUNT(*) FROM tenders').fetchone()[0]
print(f'Initial count: {initial_count}')

# 1. Delete javascript: URLs
c.execute("DELETE FROM tenders WHERE source_url LIKE 'javascript:%'")
print(f"Deleted javascript URLs: {c.rowcount}")

# 2. Delete "View" titles
c.execute("DELETE FROM tenders WHERE title = 'View'")
print(f"Deleted 'View' titles: {c.rowcount}")

# 3. Delete fiscal year titles
fiscal_years = ['2016-17', '2017-18', '2018-19', '2019-20', '2020-21', '2021-22', '2022-23', '2023-24', '2024-25', '2025-26',
                '2006-07', '2007-08', '2008-09', '2009-10', '2010-11', '2011-12', '2012-13', '2013-14', '2014-15', '2015-16']
for year in fiscal_years:
    c.execute("DELETE FROM tenders WHERE title = ?", (year,))

# 4. Delete very short titles (< 5 chars)
c.execute("DELETE FROM tenders WHERE LENGTH(title) < 5 AND title IS NOT NULL")
print(f"Deleted short titles: {c.rowcount}")

# 5. Delete empty/null URLs
c.execute("DELETE FROM tenders WHERE source_url IS NULL OR source_url = '' OR source_url = '#'")
print(f"Deleted empty URLs: {c.rowcount}")

conn.commit()

# Show final stats
final_count = c.execute('SELECT COUNT(*) FROM tenders').fetchone()[0]
print(f'\nFinal count: {final_count}')
print(f'Deleted: {initial_count - final_count} tenders')

# Show remaining by state
print('\nRemaining by state:')
c.execute('SELECT state, COUNT(*) FROM tenders GROUP BY state')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()
