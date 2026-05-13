#!/usr/bin/env bash
# Render startup script — navigates into the Q&A_Agent subdirectory
# and launches the FastAPI server. Using a shell script avoids the
# special-character issue with & in the directory name on Render.
set -e
cd "$(dirname "$0")/Q&A_Agent"
exec uvicorn api.server:app --host 0.0.0.0 --port "${PORT:-8000}"
