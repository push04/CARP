import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_options = {
    'packages': [],
    'excludes': [],
    'include_files': ['templates/']  # Include template folder
}

executables = [
    Executable('app.py', target_name='TenderIntelligenceDashboard.exe', base='Win32GUI' if sys.platform=='win32' else None)
]

setup(
    name='Tender Intelligence Dashboard',
    version='1.0',
    description='Advanced Tender Intelligence Dashboard with AI capabilities',
    options={'build_exe': build_options},
    executables=executables
)