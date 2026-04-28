# 01 — Architecture

## Process map

```
┌──────────────────────────────────────────────────────────────────────┐
│ start.sh                                                             │
│                                                                      │
│  ┌────────────────────┐   ┌─────────────────────┐   ┌─────────────┐  │
│  │ OpenClaw Gateway   │   │ FastAPI backend     │   │ Vite (dev)  │  │
│  │ v2026.4.25         │◄──┤ uvicorn main:app    │◄──┤ frontend    │  │
│  │ ws://...:18789     │WS │ port = APP_PORT+100 │   │ APP_PORT    │  │
│  └────────────────────┘   └──────────┬──────────┘   └─────────────┘  │
│           ▲                           │ SSE                          │
│           │ Ed25519 sig +             │                              │
│           │ token query               │                              │
│           │                           ▼                              │
│           │                ┌────────────────────┐                    │
│           └─reconnect loop─┤ services/          │                    │
│                            │   gateway_bridge   │                    │
│                            │   device_auth      │                    │
│                            └────────────────────┘                    │
└──────────────────────────────────────────────────────────────────────┘
```

In production (deployed) build, Vite is replaced — the FastAPI backend
serves `frontend/dist/` as static assets (configured in
`backend/main.py`). `start.sh` still launches `npx vite` for live dev.

## Ports

| Service | Port |
| --- | --- |
| Frontend (dev) | `$APP_PORT` (3000–3099) |
| Backend (FastAPI) | `$APP_PORT + 100` |
| OpenClaw Gateway (local) | `18789` |

Backend port is computed in `backend/config.py`:
```python
app_port = os.environ.get("APP_PORT", "3000")
settings.port = int(app_port) + 100
```

## Backend modules

```
backend/
├── main.py                  FastAPI app, router mounting, SSE
├── config.py                Settings + gateway URL/token resolution + persistence
├── routers/
│   ├── gateway.py           /api/gateway/* — settings, status, RPC
│   ├── agents.py            /api/agents/*
│   ├── sessions.py          /api/sessions/*
│   ├── tasks.py
│   ├── projects.py
│   ├── debate.py
│   ├── memory.py
│   ├── office.py
│   ├── autopilot.py
│   ├── skills.py
│   └── aegis.py             security audit
├── services/
│   ├── gateway_bridge.py    WS client to OC gateway, RPC, reconnect
│   ├── device_auth.py       Ed25519 identity, signing, pairing
│   ├── sse.py               SSE broadcaster
│   ├── db.py                SQLite (WAL)
│   └── ... (one per feature)
└── .data/mission_control.db SQLite store
```

## Frontend modules

```
frontend/src/
├── App.tsx                  Router
├── pages/
│   ├── Dashboard.tsx
│   ├── Agents.tsx
│   ├── Sessions.tsx
│   ├── Tasks.tsx            kanban
│   ├── Projects.tsx
│   ├── Debate.tsx
│   ├── Memory.tsx           D3 neural graph
│   ├── Office.tsx           HTML5 canvas isometric
│   ├── Autopilot.tsx
│   ├── Skills.tsx
│   ├── Aegis.tsx
│   ├── Cost.tsx
│   └── Settings.tsx         ← rewritten this session
├── components/ui/           shadcn/ui
└── stores/                  Zustand
```

## Data flow — gateway connection

1. `services.gateway_bridge.GatewayBridge` is a singleton instantiated
   at import time. It runs a `_connection_loop` in an asyncio task.
2. Each iteration:
   - Resolve URL via `_get_gateway_url()` →
     `settings.gateway_url` (preferred) or
     `device_auth.get_gateway_url()` (fallback).
   - Build full URL via `_build_ws_url()` which appends
     `?token=<gateway_token>`.
   - Open `websockets.connect(...)` with 25 MB max frame, 15 s ping.
3. After connect, perform device auth handshake:
   - Send `device.challenge.request` (RPC).
   - Sign returned challenge with Ed25519 private key
     (`device_auth.sign(challenge)`).
   - Send `device.authenticate` with public key, signature, scopes
     `["operator.admin"]`.
4. On success, `_auth_status = "authenticated"`, `_connected = True`.
5. On `DEVICE_PAIRING_REQUIRED` error, set `_auth_status =
   "pairing_required"`, keep WS open, surface in `/api/gateway/status`.
6. RPC calls (`agents.list`, `agent.run`, etc.) go via
   `GatewayBridge.rpc(method, params)` which uses request IDs and
   waits on a future for the matching response.

## Data flow — Settings UI write

```
User edits URL/token in /settings
        │
        ▼
PUT /api/gateway/settings    ──► routers/gateway.py
        │
        ▼
gateway.update_gateway_settings(url, token)
        │
        ├── save_gateway_settings(url, token)        # config.py
        │     persists to ~/.mission-control/gateway.json
        │     updates settings.gateway_url/token in memory
        │
        └── self._ws.close()                         # forces reconnect
              connection loop wakes up, picks up new settings
              opens new WS with new token in query string
```

## Identity & secrets layout

```
~/.mission-control/
├── gateway.json              { "gateway_url": ..., "gateway_token": ... }
└── identity/
    ├── device.json           { "device_id", "public_key", "private_key" }
    └── device-auth.json      { "tokens": { "operator": {...} } }
```

Fallback (legacy / co-installed with OpenClaw):
```
~/.openclaw/
├── openclaw.json             gateway config (read for autodetection)
└── identity/
    ├── device.json
    └── device-auth.json
```

## Deployment topology

The repo includes a Render deployment config (added in commit
`4f4df47`). The deployed build:
- Backend serves built frontend from `frontend/dist/`.
- Connects to a gateway via env vars (`MC_GATEWAY_URL` /
  `MC_GATEWAY_TOKEN`).
- Identity files live in the deployed instance's home dir.
