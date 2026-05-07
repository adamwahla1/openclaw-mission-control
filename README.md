# OpenClaw Mission Control

> The definitive agent orchestration dashboard for OpenClaw.

Connects to an OpenClaw Gateway over WebSocket and provides a real-time
React dashboard for managing agents, sessions, tasks, projects, debates,
memory, a virtual office, autopilot pipelines, skills, and cost tracking.

---

## TL;DR — Run it

```bash
./start.sh
```

That boots everything: a local OpenClaw gateway (v2026.4.25), the FastAPI
backend, and the Vite dev frontend.

- **Frontend** → http://localhost:3000
- **Backend** → http://localhost:3100 (auto: `$APP_PORT + 100`)

To use a remote gateway instead:

```bash
export MC_GATEWAY_URL="wss://your-gateway.example.com"
export MC_GATEWAY_TOKEN="xxxxx"
./start.sh
```

**Remote gateway notes:**
- MC auto-converts `https://` URLs to `wss://` for WebSocket compatibility.
- MC uses **token-only auth** for remote gateways (no device pairing needed).
- Your token must have `operator.read` scope on the gateway side for full
  functionality (agents list, channels, etc.). If you see
  `"missing scope: operator.read"`, add scopes on the gateway, then click
  "Save & Reconnect" in MC Settings.
- When a remote gateway is configured, `start.sh` skips the local OpenClaw
  gateway bootstrap (no 60s wait).

---

## What this is

OpenClaw Mission Control (MC) is a **full-stack web dashboard** that acts as
an `operator` client to an OpenClaw Gateway. You can use it to:

-   Spawn and monitor agents in real time
-   Run multi-agent debates
-   Manage tasks on a Kanban board
-   Track projects and sessions
-   Visualize the memory neural map (D3.js)
-   Navigate the isometric virtual office (HTML5 Canvas)
-   Run autopilot pipelines with the Skills Hub
-   Audit costs and security posture

All AI / LLM calls go through the OpenClaw Gateway — MC never speaks to
providers directly.

---

## Architecture

```
+--------------+    SSE     +--------------+   WebSocket   +--------------+
|   React 19   |<----------|  FastAPI     | ----------->  |   OpenClaw   |
|   + Vite     |            |   Backend    |  Ed25519 sig  |   Gateway    |
|   + Tailwind |            |   (Python)   |  + token      |              |
+--------------+            +--------------+               +--------------+
     ^                                              |
     |                                             WS
     v                                              v
shadcn/ui + Zustand                          Real-Time events (agents,
                                             sessions, execution)
```

| Layer | Technology |
| --- | --- |
| **Frontend** | React 19 (Vite, TypeScript, Tailwind CSS, shadcn/ui, Zustand) |
| **Backend** | FastAPI + Python 3.11 |
| **Database** | SQLite (WAL mode) |
| **Real-time** | WebSocket backend <-> gateway; SSE frontend <-> backend |
| **Identity** | Ed25519 device keypair, standalone under `~/.mission-control/identity/` |
| **Gateway** | OpenClaw CLI `gateway run` (v2026.4.25) |

---

## Features by Phase

| Phase | Feature | Status |
| --- | --- | --- |
| 1 | Tasks Hub (Kanban, real-time sessions) | Done |
| 2 | Projects + Debate Arena (multi-agent) | Done |
| 3 | Memory Neural Map (D3.js) + Virtual Office (Canvas) | Done |
| 4 | Autopilot pipelines + Skills Hub + Aegis Security + Cost Dashboard | Done |
| -- | **Settings** (gateway URL/token, diagnostics, reconnect) | Done |

---

## Prerequisites

- **Node.js** >= 20
- **Python** >= 3.11
- **uv** (Python package manager)
- (Optional) **npm** — for local OpenClaw gateway install

Install uv if you don't have it:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install OpenClaw locally (only if you want the auto-start gateway):
```bash
cd .oc-v25
npm init -y
npm install openclaw@2026.4.25
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/adamwahla1/openclaw-mission-control.git
cd openclaw-mission-control

# 2. Bootstrap Python deps
uv sync

# 3. Build frontend (if deploying)
cd frontend
npm install
npm run build
cd ..

# 4. Run everything
./start.sh
```

`start.sh` will:
- Find any installed OpenClaw v2026.4.25 binary (`.oc-v25` or `.openclaw-install`)
- Create a fresh config under `/tmp/oc-home/.openclaw/`
- Boot the gateway with `--allow-unconfigured --verbose`
- Start the FastAPI backend (`uvicorn main:app --reload`)
- Start the Vite dev server (`vite --host --port $APP_PORT`)

If you already have a remote gateway running, skip the local one by
not installing the binary:
```bash
MC_GATEWAY_URL=wss://your-gw.example.com \
MC_GATEWAY_TOKEN=xxxxx \
./start.sh
```

---

## Configuration

MC resolves the gateway URL and token in this order (high -> low):

1. `MC_GATEWAY_URL` / `MC_GATEWAY_TOKEN` (env)
2. `OPENCLAW_GATEWAY_URL` / `OPENCLAW_GATEWAY_TOKEN` (env)
3. `~/.mission-control/gateway.json` (persisted)
4. Auto-detect from `~/.openclaw/openclaw.json`
5. Default `ws://127.0.0.1:18789`

You can also set this in the **Settings** page at route `/settings`.

---

## Local Gateway vs Remote Gateway

### Local (default)

- `start.sh` auto-boots OpenClaw v2026.4.25 on port `18789`
- Uses a sandbox config with:
    - `pricing.bootstrap: false`  -- fixes the v24 CPU-spin bug
    - `plugins.deny: ["bonjour", "phone-control", "talk-voice"]`
- MC connects to `ws://127.0.0.1:18789` with a generated token
- No device pairing required (`--allow-unconfigured`)

### Remote / VPS

- Set `MC_GATEWAY_URL=wss://your-gateway.example.com`
- Set `MC_GATEWAY_TOKEN=...`
- MC will connect via WebSocket secure (`wss://`)
- The device must be **approved** on the gateway side
- Inside MC you will see `auth_status: pairing_required`
- Contact the gateway admin to approve the device, then click
    **Reconnect** in Settings

---

## API Quick Reference

### Health
```bash
curl http://localhost:3100/health
# { "status": "ok", "gateway_connected": true, ... }
```

### Gateway diagnostics
```bash
curl http://localhost:3100/api/gateway/status
# full connection + auth state
```

### List agents (live from gateway)
```bash
curl http://localhost:3100/api/gateway/agents
```

### Update settings
```bash
curl -X PUT http://localhost:3100/api/gateway/settings \
  -H 'Content-Type: application/json' \
  -d '{"url":"wss://new.example.com","token":"abcd"}'
```

---

## Project Structure

```
openclaw-mission-control/
|-- backend/
|   |-- main.py                  # FastAPI app
|   |-- config.py                # Settings, env resolution, gateway.json persistence
|   |-- routers/                 # REST endpoints (agents, sessions, tasks, projects, ...)
|   |-- services/                # Core logic
|   |   |-- gateway_bridge.py   # WS client + RPC to OpenClaw
|   |   |-- device_auth.py      # Ed25519 identity, signing, pairing
|   |   |-- db.py, sse.py, ...
|   |-- .data/mission_control.db # SQLite
|-- frontend/
|   |-- src/pages/              # Route pages (Dashboard, Agents, Settings, ...)
|   |-- src/components/ui/      # shadcn/ui components
|   |-- dist/                    # Built static assets (served by backend)
|-- docs/handover/               # Detailed handover docs (see HANDOVER.md)
|-- start.sh                     # One-script launcher
|-- render.yaml                  # Render.com deployment config
|-- tasks.json                   # Phase task tracking
```

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Module 'chokidar' not found` | Ignore -- non-fatal warning from OpenClaw `memory-core` plugin |
| Gateway boots at 40 % CPU with no response | Upgrade to OpenClaw **v2026.4.25** and set `pricing.bootstrap: false` |
| Gateway dies silently | Add `--verbose` to the `openclaw gateway run` command |
| `DEVICE_PAIRING_REQUIRED` (local gateway) | Device must be approved on the gateway side. Use Settings -> Reconnect after approval. |
| `DEVICE_PAIRING_REQUIRED` (remote gateway) | MC now uses **token-only auth** for remote gateways. If you still see this, the gateway URL may be misclassified as local. Check that it does not contain `localhost` or `127.0.0.1`. |
| `"missing scope: operator.read"` | The gateway token has no scopes assigned. Add `operator.read` (and `operator.write`, `operator.admin`) to the token on the **gateway side** (not MC). MC auto-reconnects once scopes are added. |
| MC frontend shows `disconnected` | Check `/api/gateway/status` -- token may be wrong, URL may need `https://` → `wss://` conversion, or gateway not reachable |
| Changes to gateway settings lost | They are saved to `~/.mission-control/gateway.json`. Make sure `start.sh` doesn't overwrite them. |

Full troubleshooting, runbook, and bug notes are in `docs/handover/`.

---

## Deployment

### Render.com

1. Connect the repo on Render.
2. Use the `render.yaml` blueprint (already present at root).
3. More details in `render.yaml` and `docs/handover/01-architecture.md`.

### Environment variables for hosted MC

```bash
MC_GATEWAY_URL=wss://your-gateway.example.com
MC_GATEWAY_TOKEN=xxxxx
```

The backend serves static `frontend/dist/` when deployed. Remember to
`cd frontend && npm run build` before pushing.

---

## Development

### Testing the build

```bash
cd frontend
npm install
npm run build
```

### Type-checking

```bash
cd frontend
npx tsc --noEmit
```

### Linting

```bash
cd backend
uv run ruff check .
cd frontend
npx eslint src
```

---

## Handover Documents

For deep technical context (architecture, session changes, bug workarounds,
remote gateway setup, runbook, open issues), see:

```
docs/handover/
|-- HANDOVER.md                  # master index
|-- 01-architecture.md           # process map, ports, module tree
|-- 02-session-changes.md        # file-by-file code changes with rationale
|-- 03-openclaw-bugs.md          # bugs hit and workarounds
|-- 04-local-gateway-setup.md    # how to run OC v2026.4.25
|-- 05-remote-gateway-vps.md     # connecting to a remote gateway
|-- 06-settings-ui.md            # Settings page API + token resolution chain
|-- 07-runbook.md                # health checks, logs, common ops
|-- 08-open-issues.md            # pending work + suggested next steps
|-- 09-this-session.md           # latest session: remote gateway fixes

CHANGELOG.md                      # complete feature history from day 1
```

---

## License

MIT License -- Copyright (c) 2026 Adam Wahla.
