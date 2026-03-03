#!/usr/bin/env python3
"""
Test script to run the tender fetching system and check functionality
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, '/workspace')

from app import create_app
from app.fetchers.tender_fetcher import TenderFetcher
from app.models import Tender, FetchLog
from app import db

def test_fetch():
    """Test the fetching functionality"""
    print("Initializing application...")
    app = create_app()
    
    print("Creating database tables...")
    with app.app_context():
        db.create_all()
        print("Tables created successfully.")
        
        print("Testing fetch functionality...")
        fetcher = TenderFetcher()
        
        print("Fetching from a few sample sources...")
        sample_sources = [
            {'name': 'GEM', 'url': 'https://gem.gov.in/', 'method': 'gem'},
            {'name': 'Bihar eProc2', 'url': 'https://eproc2.bihar.gov.in/', 'method': 'bihar_eproc2'},
        ]
        
        # Test individual fetch methods
        for source in sample_sources:
            print(f"Testing {source['name']}...")
            try:
                method_name = f"_fetch_from_{source['method']}"
                if hasattr(fetcher, method_name):
                    fetch_method = getattr(fetcher, method_name)
                    tenders = fetch_method(source['url'])
                    print(f"  Retrieved {len(tenders)} tenders from {source['name']}")
                    for i, tender in enumerate(tenders[:3]):  # Show first 3
                        print(f"    {i+1}. {tender.get('title', 'No title')[:100]}...")
                else:
                    print(f"  Method {method_name} not found")
            except Exception as e:
                print(f"  Error fetching from {source['name']}: {str(e)}")
        
        # Now run a full fetch
        print("\nRunning full fetch operation...")
        result = fetcher.fetch_all()
        print(f"Fetch completed. Success: {result['success_count']}, Errors: {result['error_count']}")
        
        # Count total tenders
        total_tenders = Tender.query.count()
        print(f"\nTotal tenders in database: {total_tenders}")
        
        # Show some sample tenders
        sample_tenders = Tender.query.limit(5).all()
        print(f"\nSample of {len(sample_tenders)} tenders:")
        for i, tender in enumerate(sample_tenders):
            print(f"  {i+1}. {tender.title[:100]}...")
            print(f"      Source: {tender.source_portal}")
            print(f"      State: {tender.state}")
            print(f"      Verification Score: {tender.verification_score}")
        
        # Show recent fetch logs
        recent_logs = FetchLog.query.order_by(FetchLog.created_at.desc()).limit(5).all()
        print(f"\nRecent fetch logs ({len(recent_logs)}):")
        for log in recent_logs:
            print(f"  {log.source_portal}: {log.success_count} success, {log.error_count} errors")

if __name__ == "__main__":
    test_fetch()