#!/usr/bin/env bash
# ==============================================================================
# B-SHIELD (IBVAP) — Autonomous Demo & Development Launch Script
# Intelligent Border Video Analytics Platform
# Compatible with Linux and macOS environments
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "======================================================================"
echo "      B-SHIELD (IBVAP) — AI-POWERED BORDER SURVEILLANCE PLATFORM     "
echo "======================================================================"
echo "Target Directory: $ROOT_DIR"

# 1. Dependency Pre-Flight Checks
command -v python3 >/dev/null 2>&1 || { echo >&2 "[ERROR] python3 is required but not installed. Aborting."; exit 1; }
command -v node >/dev/null 2>&1 || { echo >&2 "[ERROR] node is required but not installed. Aborting."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo >&2 "[ERROR] npm is required but not installed. Aborting."; exit 1; }

# 2. Virtual Environment Setup
cd "$ROOT_DIR/backend"
if [ ! -d ".venv" ]; then
    echo "[SETUP] Creating Python virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "[SETUP] Ensuring backend dependencies are installed..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create runtime directories
mkdir -p uploads/persons snapshots sample_videos

# 3. Frontend Setup
cd "$ROOT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "[SETUP] Installing frontend npm packages..."
    npm ci || npm install
fi

# 4. Database Seeding
cd "$ROOT_DIR/backend"
echo "[SETUP] Populating demo database records..."
python -m database.seed || echo "[WARNING] MongoDB seed skipped or DB running remotely."

# 5. Process Lifecycle Management & Graceful Cleanup
cleanup() {
    echo ""
    echo "[SHUTDOWN] Terminating B-SHIELD background servers..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
    echo "[SHUTDOWN] Cleanup complete. Exiting."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 6. Start Backend Server
cd "$ROOT_DIR/backend"
echo "[START] Launching FastAPI backend on http://127.0.0.1:8000 ..."
python -m uvicorn main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# 7. Start Frontend Dev Server
cd "$ROOT_DIR/frontend"
echo "[START] Launching Vite frontend on http://localhost:5173 ..."
npm run dev -- --host 127.0.0.1 --port 5173 &
FRONTEND_PID=$!

sleep 3
echo ""
echo "======================================================================"
echo " B-SHIELD SURVEILLANCE COMMAND CENTER IS ACTIVE"
echo " Web Console:    http://localhost:5173"
echo " Backend API:    http://127.0.0.1:8000"
echo " API Docs (UI):  http://127.0.0.1:8000/docs"
echo ""
echo " Demo Accounts:"
echo "   - Admin:    admin    / IBVAP@123"
echo "   - Operator: operator / Operator@123"
echo "   - Viewer:   viewer   / Viewer@123"
echo "======================================================================"
echo "Press Ctrl+C to terminate all services."
echo ""

wait
