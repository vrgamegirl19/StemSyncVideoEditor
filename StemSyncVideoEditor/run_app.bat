@echo off
cd /d "%~dp0"

if not exist venv\Scripts\activate (
    echo ERROR: Virtual environment not found.
    echo Please run install.bat first.
    pause
    exit /b
)

call venv\Scripts\activate
python app.py

pause
