#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/Q&A_Agent"
exec uvicorn api.server:app --host 0.0.0.0 --port "${PORT:-8000}"
