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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main function to run the application"""
    print("="*60)
    print("TENDER SCRAPER AI - PORTABLE VERSION")
    print("="*60)
    
    # Import from app factory
    from app import create_app
    from app.extensions import db
    
    app = create_app()
    
    print("Initializing database...")
    with app.app_context():
        db.create_all()
    
    print("\nApplication ready!")
    print("Access the web interface at: http://localhost:5000")
    print("="*60)
    
    try:
        app.run(host='0.0.0.0', port=5000, threaded=True, debug=True)
    except KeyboardInterrupt:
        print("\nShutting down application...")
        print("Goodbye!")


if __name__ == "__main__":
    main()