#!/bin/bash
# start_frontend.sh
# ─────────────────
# Starts the React development server for the Q&A Agent UI
#
# Usage:
#     bash start_frontend.sh
#     # or on Windows:
#     # start_frontend.bat

cd frontend
npm install
npm run dev
