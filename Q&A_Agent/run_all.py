#!/usr/bin/env python
"""
run_all.py
──────────
Single command to start both the API and frontend servers.

Usage:
    python run_all.py

This will:
  1. Install all dependencies
  2. Start the FastAPI server on port 8000
  3. Open the React UI in your browser at http://localhost:5173
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def main():
    print("=" * 70)
    print("  Q&A Agent — API + React Frontend Starter")
    print("=" * 70)
    print()

    # Install Python dependencies
    print("📦 Installing Python dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=False)
    print("✓ Python dependencies installed\n")

    # Install frontend dependencies
    frontend_dir = Path("frontend")
    if frontend_dir.exists():
        print("📦 Installing Node.js dependencies...")
        result = subprocess.run(
            ["npm", "install", "--quiet"],
            cwd=frontend_dir,
            capture_output=True,
        )
        if result.returncode == 0:
            print("✓ Node dependencies installed\n")
        else:
            print("⚠️  npm install failed (ensure Node.js is installed)\n")

    print("=" * 70)
    print("  Starting servers...")
    print("=" * 70)
    print()

    # Start API server
    print("🚀 Starting FastAPI server (port 8000)...")
    api_process = subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "api.server:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ])

    # Wait for API to start
    time.sleep(3)

    # Start frontend dev server
    print("🚀 Starting React dev server (port 5173)...")
    print()

    frontend_process = None
    if frontend_dir.exists():
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
        )

    print("\n" + "=" * 70)
    print("  ✅ All servers started!")
    print("=" * 70)
    print()
    print("  📍 API:                 http://localhost:8000")
    print("  📖 API Docs:            http://localhost:8000/docs")
    print("  🎨 Frontend:            http://localhost:5173")
    print()
    print("  Press Ctrl+C to stop all servers")
    print()
    print("=" * 70)

    # Open browser to frontend
    try:
        webbrowser.open("http://localhost:5173")
    except Exception:
        pass

    # Wait for interrupt
    try:
        api_process.wait()
    except KeyboardInterrupt:
        print("\n\nShutting down servers...")
        api_process.terminate()
        if frontend_process:
            frontend_process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
