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

# ── Skip local OpenClaw Gateway when remote is configured ──
# Check for persisted remote gateway config
_REMOTE_GW=""
_MC_CFG="$HOME/.mission-control/gateway.json"
if [ -f "$_MC_CFG" ]; then
    _REMOTE_GW=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('gateway_url',''))" "$_MC_CFG" 2>/dev/null)
fi
if [ -n "$MC_GATEWAY_URL" ] || [ -n "$OPENCLAW_GATEWAY_URL" ] || [ -n "$_REMOTE_GW" ]; then
    echo "🔗 Using remote OpenClaw Gateway (local gateway skipped)"
else
    echo "⚠️  No remote gateway configured. Set gateway URL in Settings or via MC_GATEWAY_URL."
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
