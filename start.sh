#!/bin/bash
set -e
cd "$(dirname "$0")"

# Virtualenv aktivieren falls vorhanden
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Worker starten
python3 worker.py &
WORKER_PID=$!
echo "[start.sh] Worker PID: $WORKER_PID"

# FastAPI server starten
python3 -m uvicorn server:app --host 0.0.0.0 --port 8501 --reload &
SERVER_PID=$!
echo "[start.sh] Server PID: $SERVER_PID"

cleanup() {
    echo "Beende Worker und Server..."
    kill $WORKER_PID $SERVER_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "DIRESO Agent Board läuft auf http://localhost:8501"
wait
