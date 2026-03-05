"""Run the app with debug mode to see the actual error"""
import traceback
from app import create_app

app = create_app()

# Simulate what the live server does when it handles a request to /
with app.test_request_context('/'):
    from app.main import index
    try:
        result = index()
        print(f"SUCCESS: Got response")
    except Exception as e:
        print(f"ERROR on /: {e}")
        traceback.print_exc()

# Now test with the actual WSGI app (closer to what the server does)
print("\n--- Testing with WSGI ---")
from werkzeug.test import Client
from werkzeug.wrappers import Response

c = Client(app, Response)
resp = c.get('/')
print(f"WSGI Status: {resp.status_code}")
if resp.status_code != 200:
    print(f"Body: {resp.data.decode()[:300]}")

# Check what templates are available
print("\n--- Available templates ---")
loader = app.jinja_loader
if hasattr(loader, 'loaders'):
    for l in loader.loaders:
        print(f"  Loader: {l}")
        if hasattr(l, 'searchpath'):
            for sp in l.searchpath:
                print(f"    Path: {sp}")
                import os
                if os.path.exists(sp):
                    for f in os.listdir(sp):
                        if f.endswith('.html'):
                            print(f"      -> {f}")
                else:
                    print(f"      -> PATH DOES NOT EXIST!")
