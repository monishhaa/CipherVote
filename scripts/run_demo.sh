#!/bin/bash
# SecureVote One-Command Full Stack Launcher (Backend + Frontend)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "======================================================================"
echo " STARTING SECUREVOTE VERIFIABLE VOTING SYSTEM (Backend + Frontend)"
echo "======================================================================"

# 1. Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 2. Start Backend API Server
echo "[1] Launching FastAPI Backend on http://127.0.0.1:8000 ..."
PYTHONPATH=backend ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# 3. Start React Frontend
echo "[2] Launching React + Vite Frontend on http://localhost:3000 ..."
cd frontend
npm run dev -- --host 127.0.0.1 --port 3000 &
FRONTEND_PID=$!

trap "echo 'Stopping SecureVote...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

echo ""
echo " -> Backend Swagger Docs : http://127.0.0.1:8000/docs"
echo " -> Frontend UI Portal   : http://127.0.0.1:3000"
echo ""
echo "Press [Ctrl+C] to stop all servers."
wait
