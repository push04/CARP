"""
Utility functions for the Tender Scraper application
"""
import threading
import time
from datetime import datetime
from app import create_app
from app.extensions import db
from app.models import Tender
from app.fetchers.tender_fetcher import TenderFetcher


def init_db():
    """Initialize the database and create tables if they don't exist"""
    app = create_app()
    with app.app_context():
        db.create_all()
        print("[+] Database initialized successfully")


def scraper():
    """Return a TenderFetcher instance"""
    return TenderFetcher()


def save_tenders_to_db(tenders, app=None):
    """Save fetched tenders to the database"""
    if app is None:
        app = create_app()
    with app.app_context():
        saved_count = 0
        for tender in tenders:
            # Check if tender already exists
            existing_tender = Tender.query.filter_by(tender_id=tender.get('tender_id')).first()
            if not existing_tender:
                new_tender = Tender(
                    tender_id=tender.get('tender_id'),
                    title=tender.get('title', ''),
                    description=tender.get('description'),
                    issuing_authority=tender.get('issuing_authority'),
                    department=tender.get('department'),
                    source_portal=tender.get('source_portal', 'Unknown'),
                    source_url=tender.get('source_url', ''),
                    state=tender.get('state', 'Unknown'),
                    status='open'
                )
                db.session.add(new_tender)
                saved_count += 1
        db.session.commit()
        return saved_count


def auto_fetch_job():
    """Function to automatically fetch tenders every 30 minutes"""
    print(f"[{datetime.now()}] Starting automatic tender fetch...")
    try:
        app = create_app()
        print(f"[{datetime.now()}] App created, entering context...")
        with app.app_context():
            print(f"[{datetime.now()}] Inside app context, creating fetcher...")
            fetcher = TenderFetcher()
            print(f"[{datetime.now()}] Fetcher created, calling fetch_all...")
            result = fetcher.fetch_all()
            print(f"[{datetime.now()}] Fetch result: {result}")
    except Exception as e:
        import traceback
        print(f"[{datetime.now()}] Error during auto-fetch: {str(e)}")
        traceback.print_exc()


def start_scheduler():
    """Start the scheduler to run auto-fetch every 30 minutes"""
    def run_scheduler():
        while True:
            try:
                auto_fetch_job()
                # Wait 30 minutes (1800 seconds)
                time.sleep(1800)
            except KeyboardInterrupt:
                print("Scheduler stopped.")
                break
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    return scheduler_thread