#!/bin/bash

# Start The Oracle — backend + frontend
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting The Oracle..."

# Start backend
echo "Starting backend on http://localhost:8050"
cd "$SCRIPT_DIR/backend" && uv run --project "$SCRIPT_DIR" uvicorn main:app --reload --port 8050 &
BACKEND_PID=$!

# Start frontend
echo "Starting frontend on http://localhost:5173"
cd "$SCRIPT_DIR/frontend" && npm run dev &
FRONTEND_PID=$!

# Trap Ctrl+C to kill both
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for both
wait
