#!/bin/bash
set -e

VITE_PORT="${APP_PORT:-3000}"
BACKEND_PORT=$((VITE_PORT + 100))
export VITE_PORT
export BACKEND_PORT

# OpenClaw Gateway home directory
export OPENCLAW_HOME="${OPENCLAW_HOME:-/tmp/oc-home}"

if [ -f /usr/local/lib/workshop-devguard.sh ]; then
    source /usr/local/lib/workshop-devguard.sh
    devguard_acquire "$VITE_PORT" "$BACKEND_PORT"
fi

echo "🚀 Starting OpenClaw Mission Control"
echo "   Frontend: http://localhost:$VITE_PORT"
echo "   Backend:  http://localhost:$BACKEND_PORT"

# ── Start local OpenClaw Gateway (v2026.4.25) if not already running ──
if ! python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',18789)); s.close()" 2>/dev/null; then
    # Find the openclaw binary (prefer v2026.4.25 which has pricing.bootstrap fix)
    OPENCLAW_BIN=""
    for p in \
        "$(dirname $0)/../.oc-v25/node_modules/.bin/openclaw" \
        /data/users/LJTvWmv8w3YZfYb6dMwkwprDPJv1/Workspace/.oc-v25/node_modules/.bin/openclaw \
        "$(dirname $0)/../.openclaw-install/node_modules/.bin/openclaw"; do
        if [ -x "$p" ]; then
            OPENCLAW_BIN="$p"
            break
        fi
    done

    if [ -n "$OPENCLAW_BIN" ]; then
        # Create minimal config if none exists
        if [ ! -f "$OPENCLAW_HOME/.openclaw/openclaw.json" ]; then
            mkdir -p "$OPENCLAW_HOME/.openclaw"
            GW_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(20))")
            cat > "$OPENCLAW_HOME/.openclaw/openclaw.json" << CFGEOF
{
  "gateway": {
    "mode": "local",
    "bind": "loopback",
    "auth": { "mode": "token", "token": "$GW_TOKEN" },
    "pricing": { "bootstrap": false }
  },
  "meta": { "lastTouchedVersion": "2026.4.25" },
  "models": { "mode": "merge", "providers": {} },
  "agents": { "defaults": {}, "list": [{ "id": "dev", "default": true, "identity": { "name": "Dev Agent", "theme": "assistant", "emoji": "🤖" } }] },
  "plugins": { "deny": ["bonjour", "phone-control", "talk-voice"], "entries": {} }
}
CFGEOF
            echo "   Gateway config created (token: ${GW_TOKEN:0:8}...)"
        fi

        echo "🦞 Starting OpenClaw Gateway..."
        OPENCLAW_HOME="$OPENCLAW_HOME" OPENCLAW_DISABLE_BONJOUR=1 \
            $OPENCLAW_BIN gateway run --bind loopback --port 18789 --allow-unconfigured --verbose &

        echo "⏳ Waiting for OpenClaw Gateway (up to 60s)..."
        for i in $(seq 1 60); do
            if python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',18789)); s.close()" 2>/dev/null; then
                echo "✅ Gateway ready"
                break
            fi
            sleep 1
        done
    else
        echo "⚠️  OpenClaw CLI not found. Gateway features disabled."
        echo "   Install with: npm install openclaw@2026.4.25"
    fi
else
    echo "✅ OpenClaw Gateway already running on port 18789"
fi

# ── Start backend ──
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

# ── Start frontend ──
cd frontend
npx vite --host 0.0.0.0 --port "$VITE_PORT" --strictPort &
FRONTEND_PID=$!
cd ..

echo "✅ Mission Control running"
echo "   Connect to your gateway via Settings in the UI"

# Wait for either to exit
wait $BACKEND_PID $FRONTEND_PID
