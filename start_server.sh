#!/bin/bash
# FastAPI Server Startup Script
# This script ensures the server starts from the correct directory with proper PYTHONPATH

cd "$(dirname "$0")/src" || exit 1
export PYTHONPATH="$(pwd):$PYTHONPATH"

echo "Starting FastAPI server..."
echo "Working directory: $(pwd)"
echo "PYTHONPATH: $PYTHONPATH"
echo ""

../.venv/bin/uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 --timeout-keep-alive 1800 --timeout-graceful-shutdown 30
