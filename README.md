# Tender Tracking System for Bihar & Jharkhand

A robust Python application that aggregates tenders from multiple state and central government portals, implements advanced deduplication, supplier matching, and provides a professional dashboard interface.

## Features
- Real-time tender aggregation from 100+ sources
- Advanced deduplication using AI-powered semantic analysis
- Supplier matching with price range estimation
- Professional dashboard with advanced filtering
- Auto-fetch every 30 minutes
- Beautiful PDF export with checkboxes
- Comprehensive logging and error handling

## Prerequisites
- Python 3.10+
- Google Chrome installed
- Valid OpenRouter API key

## Setup Instructions

1. Create a `.env` file with your API keys:
```bash
OPENROUTER_API_KEY=your_openrouter_api_key_here
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

2. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

3. Run the application using the provided batch file:
```bash
run_app.bat
```

## Environment Variables
- `OPENROUTER_API_KEY` - OpenRouter API key for AI features
- `SMTP_USERNAME` - Email username for notifications
- `SMTP_PASSWORD` - Email password for notifications
- `SMTP_SERVER` - SMTP server address
- `SMTP_PORT` - SMTP server port
- `DATABASE_URL` - Database connection string (optional, defaults to SQLite)

## Usage
The application will start a Flask server on http://localhost:5000 and automatically open in Chrome. You can:
- View all tenders in the dashboard
- Filter and sort by various criteria
- Toggle auto-fetch mode
- Export tenders to CSV/PDF
- View supplier recommendations for each tender
- Manually fetch from specific sources

## Legal Considerations
This application respects robots.txt policies and implements rate limiting. Users are responsible for ensuring their usage complies with individual portal terms of service and applicable laws regarding public procurement data access.