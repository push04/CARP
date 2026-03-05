"""Test script to verify tender fetching works"""
from app import create_app
from app.fetchers.tender_fetcher import TenderFetcher
from app.extensions import db
from app.models import Tender

app = create_app()
with app.app_context():
    print("=== Testing TenderFetcher ===")
    fetcher = TenderFetcher()
    print(f"Sources count: {len(fetcher.sources)}")
    print(f"AI analyzer available: {fetcher.ai_analyzer is not None}")
    
    # Show first 3 sources
    for i, src in enumerate(fetcher.sources[:3]):
        print(f"  Source {i+1}: {src['name']} -> {src['url'][:60]}...")
    
    # Try fetching from the first source
    if fetcher.sources:
        source = fetcher.sources[0]
        print(f"\nTesting fetch from: {source['name']}")
        try:
            tenders = fetcher._fetch_from_source(source)
            print(f"Result: {len(tenders) if tenders else 0} tenders found")
            if tenders:
                for t in tenders[:3]:
                    print(f"  - {t.get('title', 'NO TITLE')[:60]}")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
    
    # Check current DB state
    total = Tender.query.count()
    valid = Tender.query.filter(Tender.title.isnot(None), Tender.title != '').count()
    print(f"\nDB: {total} total, {valid} with valid titles")