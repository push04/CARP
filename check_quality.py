import sqlite3

conn = sqlite3.connect('instance/tenders.db')
c = conn.cursor()

print("=== Quality Analysis ===")

# Check how many have meaningful titles (not "View", "2016-17", etc)
c.execute('''SELECT COUNT(*) FROM tenders WHERE 
    title IS NOT NULL 
    AND title != ''
    AND title != 'View'
    AND title != '2016-17'
    AND title != '2017-18'
    AND title != '2018-19'
    AND title != '2019-20'
    AND title != '2020-21'
    AND title != '2021-22'
    AND title != '2022-23'
    AND title != '2023-24'
    AND title != '2024-25'
    AND title != '2025-26'
    AND LENGTH(title) > 10''')
meaningful = c.fetchone()[0]
print(f'Tenders with meaningful titles: {meaningful}')

# Check how many have valid URLs (not javascript:)
c.execute('''SELECT COUNT(*) FROM tenders WHERE 
    source_url IS NOT NULL 
    AND source_url != ''
    AND source_url NOT LIKE 'javascript:%'
    AND source_url NOT LIKE '#'
    AND source_url NOT LIKE 'http://' 
    AND source_url NOT LIKE 'https://' ''')
valid_url = c.fetchone()[0]
print(f'Tenders with valid URLs: {valid_url}')

# Show breakdown of title lengths
print('\nTitle length distribution:')
c.execute('''SELECT 
    CASE 
        WHEN LENGTH(title) < 5 THEN 'Very Short (<5)'
        WHEN LENGTH(title) < 20 THEN 'Short (5-19)'
        WHEN LENGTH(title) < 50 THEN 'Medium (20-49)'
        ELSE 'Long (50+)'
    END as category,
    COUNT(*) as count
FROM tenders 
WHERE title IS NOT NULL
GROUP BY category''')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Show some examples of bad data
print('\nExamples of bad titles:')
c.execute("SELECT title, state, source_portal FROM tenders WHERE LENGTH(title) < 10 OR title = 'View' LIMIT 10")
for row in c.fetchall():
    print(f'  "{row[0]}" | {row[1]} | {row[2]}')

conn.close()
