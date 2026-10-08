#!/usr/bin/env bash
# GateMaster Quickstart Runner (GATE CSE 2027)

echo "=============================================="
echo " Starting GateMaster (GATE CSE 2027 Preparation)"
echo " Target: 80+ Marks / AIR < 100"
echo "=============================================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Start FastAPI backend
echo "[1/2] Starting FastAPI Backend on port 8000..."
cd "$ROOT_DIR/backend"
PYTHONPATH="$ROOT_DIR/backend" ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# 2. Start Next.js frontend
echo "[2/2] Starting Next.js Frontend on port 3000..."
cd "$ROOT_DIR/frontend"
npm run dev -- -p 3000 &
FRONTEND_PID=$!

cleanup() {
    echo ""
    echo "Shutting down GateMaster servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "GateMaster is up and running!"
echo "  • Frontend UI: http://localhost:3000"
echo "  • Backend API: http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services."

wait
