import requests
r = requests.get('http://localhost:5000/')
print(f"Status: {r.status_code}")
print(f"Length: {len(r.text)} chars")
if r.status_code != 200:
    print(f"ERROR BODY: {r.text[:500]}")
else:
    print("HOME PAGE LOADS OK")

r2 = requests.get('http://localhost:5000/tender/16090')
print(f"\nTender detail status: {r2.status_code}")
if r2.status_code == 200:
    print("TENDER DETAIL PAGE LOADS OK")
else:
    print(f"ERROR: {r2.text[:500]}")
