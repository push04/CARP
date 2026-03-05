"""Test the app routes to find errors"""
import traceback
from app import create_app
from app.extensions import db

app = create_app()
app.config['TESTING'] = True

with app.test_client() as client:
    print("=== Testing GET / ===")
    try:
        resp = client.get('/')
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Response: {resp.data.decode()[:500]}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
    
    print("\n=== Testing GET /tender/1 ===")
    try:
        resp = client.get('/tender/1')
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Response: {resp.data.decode()[:500]}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

    print("\n=== Testing GET /api/tenders ===")
    try:
        resp = client.get('/api/tenders')
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            import json
            data = json.loads(resp.data)
            print(f"Total tenders: {data.get('total', 'N/A')}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

    print("\n=== Testing GET /health ===")
    try:
        resp = client.get('/health')
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.data.decode()[:200]}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
