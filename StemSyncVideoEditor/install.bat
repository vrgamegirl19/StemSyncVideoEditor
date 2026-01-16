@echo off
cd /d "%~dp0"

echo =========================================
echo Beat-Locked Auto Editor - Installer
echo =========================================
echo.

REM -------------------------------
REM Check Python
REM -------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not on PATH.
    echo.
    echo Please install Python 3.10 or newer:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during install.
    echo.
    pause
    exit /b
)

echo Python detected.

REM -------------------------------
REM Check FFmpeg
REM -------------------------------
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: FFmpeg is not installed or not on PATH.
    echo.
    echo This app requires FFmpeg for video rendering.
    echo.
    echo Download FFmpeg:
    echo https://ffmpeg.org/download.html
    echo.
    echo After installing, make sure ffmpeg.exe is on PATH.
    echo.
    pause
    exit /b
)

echo FFmpeg detected.

REM -------------------------------
REM Create venv
REM -------------------------------
if not exist venv (
    echo.
    echo Creating virtual environment...
    python -m venv venv
)

REM -------------------------------
REM Activate venv
REM -------------------------------
call venv\Scripts\activate
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b
)

REM -------------------------------
REM Install dependencies
REM -------------------------------
echo.
echo Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    echo Check your internet connection and try again.
    echo.
    pause
    exit /b
)

echo.
echo =========================================
echo Installation complete!
echo.
echo To run the app:
echo   Double-click run_app.bat
echo =========================================
pause
