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

# Start OpenClaw Gateway if not already running
if ! python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',18789)); s.close()" 2>/dev/null; then
    echo "🦞 Starting OpenClaw Gateway..."
    # Find openclaw binary
    OPENCLAW_BIN=""
    if command -v openclaw &>/dev/null; then
        OPENCLAW_BIN="openclaw"
    elif [ -f "$HOME/.openclaw-install/node_modules/.bin/openclaw" ]; then
        OPENCLAW_BIN="$HOME/.openclaw-install/node_modules/.bin/openclaw"
    else
        # Search for it
        for p in /data/users/*/.openclaw-install/node_modules/.bin/openclaw; do
            if [ -x "$p" ]; then
                OPENCLAW_BIN="$p"
                break
            fi
        done
    fi

    if [ -n "$OPENCLAW_BIN" ]; then
        $OPENCLAW_BIN gateway &
        GATEWAY_PID=$!
        # Wait for gateway to be ready (can take up to 30s)
        echo "⏳ Waiting for OpenClaw Gateway..."
        for i in $(seq 1 60); do
            if python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',18789)); s.close()" 2>/dev/null; then
                echo "✅ Gateway ready"
                break
            fi
            sleep 1
        done
    else
        echo "⚠️  OpenClaw CLI not found. Gateway features disabled."
    fi
else
    echo "✅ OpenClaw Gateway already running on port 18789"
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
