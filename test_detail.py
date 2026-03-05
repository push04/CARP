"""Test tender detail route with valid ID"""
import traceback
from app import create_app

app = create_app()
app.config['TESTING'] = True

with app.test_client() as client:
    print("=== Testing GET /tender/16090 ===")
    try:
        resp = client.get('/tender/16090')
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            html = resp.data.decode()
            print(f"Page loaded OK! Length: {len(html)} chars")
            # Check for key elements
            if 'tender-detail-card' in html:
                print("  ✓ tender-detail-card found")
            if 'Find Supplier' in html:
                print("  ✓ Find Supplier button found")
            if 'Export PDF' in html:
                print("  ✓ Export PDF button found")
            if 'Copy URL' in html:
                print("  ✓ Copy URL button found")
        else:
            print(f"Response: {resp.data.decode()[:1000]}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
