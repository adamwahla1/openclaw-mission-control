# 07 — Runbook

## 7.1 Start everything

```bash
cd /data/users/LJTvWmv8w3YZfYb6dMwkwprDPJv1/Workspace/openclaw_mission_control
./start.sh
```

Order of operations inside `start.sh`:
1. Resolve `VITE_PORT = $APP_PORT`, `BACKEND_PORT = APP_PORT + 100`.
2. Devguard releases stale listeners on those ports.
3. If port 18789 isn't already listening, start a local OpenClaw
   gateway (v2026.4.25) writing to `/tmp/openclaw-gateway.log`.
4. Wait up to 60 s for gateway port to open.
5. Start FastAPI backend (`uvicorn main:app --reload`).
6. Wait up to 15 s for `/api/health`.
7. Start `npx vite --strictPort` for the frontend.
8. `wait` on backend & frontend PIDs.

To start with a remote gateway and skip the local one, just don't
have the openclaw binary discoverable. Or, simpler:

```bash
MC_GATEWAY_URL=wss://your-gw.example.com \
MC_GATEWAY_TOKEN=xxxx \
./start.sh
```

(The local-gateway block in `start.sh` only runs if port 18789 isn't
already listening; if you don't want a local gateway at all but the
binary is present, comment the block out — or kill 18789 manually.)

## 7.2 Stop everything

```bash
# Frontend + backend
pkill -f "uvicorn main:app"
pkill -f "vite --host"

# Local gateway
pkill -f "openclaw gateway run"
```

## 7.3 Health checks

```bash
# MC backend liveness
curl -s http://localhost:$BACKEND_PORT/health | jq

# Gateway diagnostics
curl -s http://localhost:$BACKEND_PORT/api/gateway/status | jq

# Live agents from gateway
curl -s http://localhost:$BACKEND_PORT/api/gateway/agents | jq

# Settings (URL + token preview only)
curl -s http://localhost:$BACKEND_PORT/api/gateway/settings | jq
```

End-of-session known-good output:

```json
GET /health
{"status":"ok",
 "gateway_connected":true,
 "gateway_authenticated":true,
 "auth_status":"authenticated",
 "version":"0.1.0"}

GET /api/gateway/agents
{"ok":true,
 "agents":[{"id":"main","workspace":"/tmp/oc-home/.openclaw/workspace"}]}
```

## 7.4 Logs

| What | Where |
| --- | --- |
| Local OpenClaw gateway | `/tmp/openclaw-gateway.log` |
| Backend (uvicorn) | stdout of `start.sh` |
| Frontend (vite) | stdout of `start.sh` |

Tail gateway log:
```bash
tail -f /tmp/openclaw-gateway.log
```

## 7.5 Common ops

### Change which gateway MC talks to

UI: Settings → enter URL/token → Save & Reconnect.

CLI:
```bash
curl -X PUT http://localhost:$BACKEND_PORT/api/gateway/settings \
  -H 'Content-Type: application/json' \
  -d '{"url":"wss://new-gateway.example.com","token":"abcd1234"}'
```

### Force a reconnect

```bash
curl -X POST http://localhost:$BACKEND_PORT/api/gateway/reconnect
```

### Reset MC identity (fresh device)

```bash
rm -rf ~/.mission-control/identity
# next connection MC will generate a new keypair and need to re-pair
```

### Reset persisted gateway settings

```bash
rm ~/.mission-control/gateway.json
# next start: env vars / autodetect take over
```

### Reset local gateway state

```bash
rm -rf /tmp/oc-home
./start.sh   # rebootstraps fresh config
```

## 7.6 Where ports/tokens come from at a glance

```
APP_PORT          ← sandbox / Vite preview
BACKEND_PORT      ← APP_PORT + 100
Gateway port      ← 18789 (local) or implicit in URL (remote)
Gateway token     ← env var > ~/.mission-control/gateway.json
                    > ~/.openclaw/openclaw.json
Device keypair    ← ~/.mission-control/identity/device.json
                    (fallback ~/.openclaw/identity/device.json)
```
