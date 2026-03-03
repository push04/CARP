@echo off
echo Setting up Tender Tracking System...

REM Check if virtual environment exists, if not create it
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies if requirements.txt exists
if exist requirements.txt (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Install playwright browsers if not already installed
echo Installing Playwright browsers...
playwright install chromium

REM Set environment variables
set OPENROUTER_API_KEY=%OPENROUTER_API_KEY%
set DATABASE_URL=sqlite:///tenders.db

REM Start the Flask application in background
echo Starting Tender Tracking System...
start "" python app/main.py

REM Wait a moment for the server to start
timeout /t 3 /nobreak >nul

REM Open the dashboard in Chrome
start "" chrome http://localhost:5000

echo Application started successfully!
echo The dashboard is now open in Chrome.
echo Press any key to exit...
pause >nul