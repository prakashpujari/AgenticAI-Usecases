@echo off
REM start_frontend.bat
REM ─────────────────
REM Starts the React development server for the Q&A Agent UI
REM
REM Usage:
REM     start_frontend.bat

cd frontend
call npm install
call npm run dev
pause
