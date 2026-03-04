"""
Setup script to create a single executable file for the Tender Scraper AI application
"""
import sys
import subprocess
import os
from pathlib import Path

def install_dependencies():
    """Install all required dependencies"""
    print("Installing required dependencies...")
    
    # Read requirements from the requirements.txt file
    with open('requirements.txt', 'r') as f:
        requirements = f.read().splitlines()
    
    # Install each requirement
    for req in requirements:
        if req.strip() and not req.startswith('#'):
            print(f"Installing {req}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", req])

def create_executable():
    """Create the executable using PyInstaller"""
    print("Creating executable with PyInstaller...")
    
    # Create a basic spec file for PyInstaller
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=[
        'openrouter',
        'sqlite3',
        'flask',
        'flask_cors',
        'bs4',
        'openai',
        'requests',
        'urllib3',
        'werkzeug',
        'jinja2',
        'markupsafe',
        'itsdangerous',
        'click',
        'flask_sqlalchemy',
        'sqlalchemy',
        'lxml',
        'pandas',
        'openpyxl',
        'cryptography',
        'uuid',
        'datetime',
        'threading',
        'time',
        're',
        'hashlib',
        'functools',
        'json',
        'os',
        'logging',
        'urllib',
        'collections',
        'httpx',
        'urllib.parse',
        'threading',
        'apscheduler',
        'apscheduler.schedulers',
        'apscheduler.schedulers.background',
        'flask_apscheduler',
        'selenium',
        'webdriver_manager',
        'undetected_chromedriver',
        'fake_useragent',
        'colorama',
        'gunicorn',
        'rapidfuzz',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TenderScraperAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""
    
    with open('tender_scraper_ai.spec', 'w') as f:
        f.write(spec_content)
    
    # Run PyInstaller with the spec file
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller", 
        "tender_scraper_ai.spec", 
        "--noconfirm", 
        "--clean"
    ])

def main():
    """Main function to build the executable"""
    print("Building Tender Scraper AI Executable...")
    
    try:
        # Install dependencies
        install_dependencies()
        
        # Create executable
        create_executable()
        
        print("\n" + "="*60)
        print("SUCCESS: Tender Scraper AI Executable Built!")
        print("="*60)
        print("The executable is located in ./dist/TenderScraperAI")
        print("\nTo run the application:")
        print("  1. Navigate to the dist folder")
        print("  2. Run ./TenderScraperAI (Linux/Mac) or TenderScraperAI.exe (Windows)")
        print("  3. Access the web interface at http://localhost:5000")
        print("  4. Login with username: admin, password: admin123")
        print("="*60)
        
    except subprocess.CalledProcessError as e:
        print(f"Error during build: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()