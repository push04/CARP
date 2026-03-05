"""Final comprehensive route test"""
import traceback, json
from app import create_app

app = create_app()
app.config['TESTING'] = True

results = []
with app.test_client() as client:
    routes = [
        ('GET', '/'),
        ('GET', '/health'),
        ('GET', '/metrics'),
        ('GET', '/api/tenders'),
        ('GET', '/api/tenders?medical=true'),
        ('GET', '/api/tenders?state=Bihar'),
        ('GET', '/tender/16090'),
        ('GET', '/settings'),
    ]
    
    for method, url in routes:
        try:
            resp = client.get(url)
            status = 'OK' if resp.status_code == 200 else f'FAIL({resp.status_code})'
            size = len(resp.data)
            results.append(f"  {status:>10} | {method} {url} | {size} bytes")
        except Exception as e:
            results.append(f"  ERROR     | {method} {url} | {str(e)[:60]}")

print("=" * 70)
print("ROUTE VERIFICATION RESULTS")
print("=" * 70)
for r in results:
    print(r)
print("=" * 70)

# Also test API data
with app.test_client() as client:
    resp = client.get('/api/tenders?per_page=3')
    if resp.status_code == 200:
        data = json.loads(resp.data)
        print(f"\nAPI tenders total: {data['total']}")
        print(f"Sample tenders:")
        for t in data['tenders'][:3]:
            print(f"  ID: {t['id']} | {t['title'][:50]}... | {t['source_portal']}")
    
    resp = client.get('/metrics')
    if resp.status_code == 200:
        metrics = json.loads(resp.data)
        print(f"\nMetrics:")
        for k, v in metrics.items():
            print(f"  {k}: {v}")
