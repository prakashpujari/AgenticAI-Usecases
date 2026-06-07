@echo off
setlocal enabledelayedexpansion
REM AIOps Platform - Screenshot Capture Script (Windows)
REM Usage: .\capture_screenshots.bat (with .\)
REM Or:    cmd /c capture_screenshots.bat

cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║   AIOps Platform - Automated Screenshot Capture (Windows)      ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Check if Node.js is installed
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Node.js not found!
    echo.
    echo Please install Node.js from: https://nodejs.org
    echo.
    pause
    exit /b 1
)

echo ✅ Node.js found:
node --version
echo.

REM Check if backend is running
echo 🔍 Checking if backend is running...
curl -s http://localhost:8000/health >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo ❌ Backend API is not running!
    echo.
    echo Please start the AIOps platform first:
    echo   1. Open PowerShell or Command Prompt
    echo   2. Navigate to project directory
    echo   3. Run: ./start_local.sh
    echo.
    echo Then run this script again.
    echo.
    pause
    exit /b 1
)

echo ✅ Backend API is running
echo.

REM Check if npm is installed
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ npm not found!
    echo Please install Node.js from: https://nodejs.org
    echo.
    pause
    exit /b 1
)

echo 📦 Installing Puppeteer dependencies...
call npm install puppeteer --silent
if %errorlevel% neq 0 (
    echo ❌ Failed to install Puppeteer
    echo.
    echo Try running manually:
    echo   npm install puppeteer
    echo.
    pause
    exit /b 1
)

echo ✅ Puppeteer installed
echo.

echo 🚀 Starting screenshot capture...
echo.
call node capture-screenshots.js

if %errorlevel% neq 0 (
    echo.
    echo ❌ Screenshot capture failed!
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ Screenshot capture complete!
echo.
echo 📁 Screenshots saved to: docs\screenshots\
echo.
echo Verification:
dir docs\screenshots\*.png | find /c ".png"
echo files captured.
echo.
pause
