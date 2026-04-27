#!/bin/bash
set -e

VITE_PORT="${APP_PORT:-3000}"
BACKEND_PORT=$((VITE_PORT + 100))

export VITE_PORT
export BACKEND_PORT

if [ -f /usr/local/lib/workshop-devguard.sh ]; then
    source /usr/local/lib/workshop-devguard.sh
    devguard_acquire "$VITE_PORT" "$BACKEND_PORT"
fi

echo "🚀 Starting OpenClaw Mission Control"
echo "   Frontend: http://localhost:$VITE_PORT"
echo "   Backend:  http://localhost:$BACKEND_PORT"

# Check if OpenClaw Gateway is already running (don't start it — has CPU spin bug v2026.4.5+)
if python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',18789)); s.close()" 2>/dev/null; then
    echo "✅ OpenClaw Gateway detected on port 18789"
else
    echo "⚠️  OpenClaw Gateway not running — gateway features disabled (gateway has CPU spin bug in v2026.4.5+)"
fi

# Start backend
cd backend
uv run uvicorn main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
echo "⏳ Waiting for backend..."
for i in $(seq 1 15); do
    if curl -s "http://localhost:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
        echo "✅ Backend ready"
        break
    fi
    sleep 1
done

# Start frontend
cd frontend
npx vite --host 0.0.0.0 --port "$VITE_PORT" --strictPort &
FRONTEND_PID=$!
cd ..

echo "✅ Mission Control running"

# Wait for either to exit
wait $BACKEND_PID $FRONTEND_PID
