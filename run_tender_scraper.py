"""
Portable Tender Scraper AI Application
This script runs the Tender Scraper AI application with all features
"""
import os
import sys
import threading
import time
from datetime import datetime
from flask import Flask
import sqlite3
import atexit

# Add the workspace to path to import our modules
sys.path.insert(0, '/workspace')

# Import the main app
from app import app, init_db, scraper, save_tenders_to_db

def auto_fetch_job():
    """Function to automatically fetch tenders every 30 minutes"""
    print(f"[{datetime.now()}] Starting automatic tender fetch...")
    try:
        tenders = scraper.scrape_government_portals()
        saved_count = save_tenders_to_db(tenders)
        print(f"[{datetime.now()}] Auto-fetch completed: {len(tenders)} found, {saved_count} saved to database")
    except Exception as e:
        print(f"[{datetime.now()}] Error during auto-fetch: {str(e)}")

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

def main():
    """Main function to run the application"""
    print("="*60)
    print("TENDER SCRAPER AI - PORTABLE VERSION")
    print("="*60)
    print("Initializing database...")
    
    # Initialize database
    init_db()
    
    print("Starting automatic fetch scheduler (every 30 minutes)...")
    scheduler_thread = start_scheduler()
    
    print("\nApplication ready!")
    print("Access the web interface at: http://localhost:5000")
    print("Login credentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print("\nFeatures available:")
    print("  ✓ Database view of tenders")
    print("  ✓ Dashboard with statistics")
    print("  ✓ Auto-run fetch every 30 minutes")
    print("  ✓ Manual fetch capability")
    print("  ✓ AI-powered tender analysis (using OpenRouter API)")
    print("  ✓ Export tenders to CSV")
    print("  ✓ Email drafting assistance")
    print("  ✓ Risk analysis and proposal drafting")
    print("="*60)
    
    try:
        # Start the Flask app
        app.run(host='0.0.0.0', port=5000, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down application...")
        print("Goodbye!")

if __name__ == "__main__":
    main()