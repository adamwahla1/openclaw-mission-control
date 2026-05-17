#!/bin/bash
set -e

VITE_PORT="${APP_PORT:-3000}"
BACKEND_PORT=$((VITE_PORT + 100))
export VITE_PORT
export BACKEND_PORT

# OpenClaw remains available as an optional adapter when enabled in Settings.
export OPENCLAW_HOME="${OPENCLAW_HOME:-/tmp/oc-home}"

if [ -f /usr/local/lib/workshop-devguard.sh ]; then
    source /usr/local/lib/workshop-devguard.sh
    devguard_acquire "$VITE_PORT" "$BACKEND_PORT"
fi

echo "Starting Mission Control"
echo "   Frontend: http://localhost:$VITE_PORT"
echo "   Backend:  http://localhost:$BACKEND_PORT"
echo "   Runtime:  native Mission Control"

_REMOTE_GW=""
_MC_CFG="$HOME/.mission-control/gateway.json"
if [ -f "$_MC_CFG" ]; then
    _REMOTE_GW=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('gateway_url',''))" "$_MC_CFG" 2>/dev/null)
fi
if [ -n "$MC_GATEWAY_URL" ] || [ -n "$OPENCLAW_GATEWAY_URL" ] || [ -n "$_REMOTE_GW" ]; then
    echo "Optional OpenClaw gateway config detected. Enable the adapter in Settings when needed."
else
    echo "OpenClaw is optional. Mission Control will boot in native mode."
fi

cd backend
uv run uvicorn main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!
cd ..

echo "Waiting for backend..."
for i in $(seq 1 15); do
    if curl -s "http://localhost:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
        echo "Backend ready"
        break
    fi
    sleep 1
done

cd frontend
npx vite --host 0.0.0.0 --port "$VITE_PORT" --strictPort &
FRONTEND_PID=$!
cd ..

echo "Mission Control running"
echo "   Configure OpenRouter and model defaults in Settings"

wait $BACKEND_PID $FRONTEND_PID
