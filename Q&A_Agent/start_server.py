"""
start_server.py
───────────────
Convenience script to start the FastAPI server.

Usage:
    python start_server.py

The API will be available at http://localhost:8000
API docs at http://localhost:8000/docs
"""

import subprocess
import sys
from pathlib import Path

# Ensure dependencies are installed
print("📦 Installing dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=False)

# Install frontend dependencies if not already installed
frontend_dir = Path("frontend")
if frontend_dir.exists():
    print("📦 Installing frontend dependencies...")
    subprocess.run(
        ["npm", "install", "--quiet"],
        cwd=frontend_dir,
        capture_output=True,
    )

# Start the FastAPI server
print("\n🚀 Starting Q&A Agent API Server...")
print("📍 API endpoint: http://localhost:8000")
print("📖 API documentation: http://localhost:8000/docs")
print("🔄 Health check: http://localhost:8000/health\n")

try:
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "api.server:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ])
except KeyboardInterrupt:
    print("\n\nServer stopped.")
    sys.exit(0)
