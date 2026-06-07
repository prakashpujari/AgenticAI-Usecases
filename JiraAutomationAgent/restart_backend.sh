#!/bin/bash

# Kill all Python uvicorn processes
pkill -9 -f "uvicorn" || true
sleep 2

# Start backend with env vars
cd "$(dirname "$0")/backend"
export $(cat ../.env.local | xargs)

echo "Starting backend on port 8000..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
