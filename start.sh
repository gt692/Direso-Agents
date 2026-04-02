#!/bin/bash
# start.sh — Startet DIRESO Agent Board (Streamlit + Worker)
# Lokal:  ./start.sh
# VPS:    nohup ./start.sh &

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Virtualenv aktivieren falls vorhanden
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

PORT=${PORT:-8501}
HOST=${HOST:-0.0.0.0}

echo "========================================"
echo "  DIRESO Agent Board"
echo "  http://$HOST:$PORT"
echo "========================================"

# Worker als Hintergrundprozess starten
echo "[start.sh] Worker wird gestartet..."
python worker.py &
WORKER_PID=$!
echo "[start.sh] Worker PID: $WORKER_PID"

# Cleanup beim Beenden
cleanup() {
    echo "[start.sh] Beende Worker ($WORKER_PID)..."
    kill $WORKER_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Streamlit starten
echo "[start.sh] Streamlit wird gestartet auf Port $PORT..."
python -m streamlit run app.py \
    --server.port "$PORT" \
    --server.address "$HOST" \
    --server.headless true \
    --browser.gatherUsageStats false

# Falls Streamlit unerwartet beendet wird
cleanup
