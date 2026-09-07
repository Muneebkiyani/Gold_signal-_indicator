#!/usr/bin/env bash
# ==============================================================================
# XAUUSD Gold Signal Alert System — Unified Server Startup
# ==============================================================================
# Usage:
#   ./start.sh
# ==============================================================================

set -e

# Resolve directory paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_DIR/gold-signal-system" ]; then
    ROOT_DIR="$SCRIPT_DIR/gold-signal-system"
else
    ROOT_DIR="$SCRIPT_DIR"
fi

BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# Ensure Node & npm are in PATH
export PATH="/Users/mac/Downloads/node-v16.20.2-darwin-x64/bin:/Users/mac/.local/bin:/usr/local/bin:$PATH"

echo "=================================================================="
echo "   🚀 Starting XAUUSD Gold Signal Alert System"
echo "=================================================================="

# 1. Clean up any existing processes on ports 8000 and 5173
echo "• Checking ports 8000 (backend) & 5173 (frontend)..."
PID_BACKEND=$(lsof -ti:8000 2>/dev/null || true)
if [ -n "$PID_BACKEND" ]; then
    echo "  → Freeing port 8000 (PID $PID_BACKEND)..."
    kill -9 $PID_BACKEND 2>/dev/null || true
fi

PID_FRONTEND=$(lsof -ti:5173 2>/dev/null || true)
if [ -n "$PID_FRONTEND" ]; then
    echo "  → Freeing port 5173 (PID $PID_FRONTEND)..."
    kill -9 $PID_FRONTEND 2>/dev/null || true
fi

# Cleanup on exit (Ctrl+C)
cleanup() {
    echo ""
    echo "Shutting down all servers..."
    if [ -n "$BACKEND_PID" ]; then kill -TERM "$BACKEND_PID" 2>/dev/null || true; fi
    if [ -n "$FRONTEND_PID" ]; then kill -TERM "$FRONTEND_PID" 2>/dev/null || true; fi
    wait 2>/dev/null || true
    echo "✅ All servers stopped cleanly."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 2. Start Backend
echo "• Starting Backend (FastAPI / Uvicorn on :8000)..."
cd "$BACKEND_DIR"
if [ ! -d ".venv" ]; then
    echo "❌ Error: backend/.venv not found!"
    exit 1
fi
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to become healthy
echo "• Waiting for backend to initialize..."
for i in {1..15}; do
    if curl -s http://localhost:8000/api/status >/dev/null 2>&1; then
        echo "  → Backend is ready! ✅"
        break
    fi
    sleep 1
done

# 3. Start Frontend
echo "• Starting Frontend (port :5173)..."
cd "$FRONTEND_DIR"
if command -v npm >/dev/null 2>&1; then
    npm run dev -- --host 0.0.0.0 --port 5173 &
    FRONTEND_PID=$!
elif [ -f "$FRONTEND_DIR/serve_frontend.py" ]; then
    echo "  → Node/npm not found. Serving pre-built dashboard + API proxy on :5173 ✅"
    python3 "$FRONTEND_DIR/serve_frontend.py" >/dev/null 2>&1 &
    FRONTEND_PID=$!
elif [ -d "$FRONTEND_DIR/dist" ]; then
    echo "  → Serving pre-built dashboard on :5173 ✅"
    python3 -m http.server 5173 --directory "$FRONTEND_DIR/dist" >/dev/null 2>&1 &
    FRONTEND_PID=$!
else
    echo "  ⚠️ Warning: Neither npm nor frontend/dist found."
fi

sleep 2

echo "=================================================================="
echo "   🟢 SYSTEM IS ONLINE & LIVE"
echo "=================================================================="
echo "   📊 Frontend Dashboard: http://localhost:5173"
echo "   ⚙️  Backend API / Docs: http://localhost:8000/docs"
echo "   📡 Live SSE Stream:    http://localhost:8000/api/stream"
echo "=================================================================="
echo "   Press Ctrl+C to stop all servers."
echo "=================================================================="

# Keep script running and wait for background jobs
wait "$BACKEND_PID" "$FRONTEND_PID"
