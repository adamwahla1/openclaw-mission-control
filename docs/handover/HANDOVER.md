# OpenClaw Mission Control — Handover Document

**Date:** 2026-05-07 (updated)
**Repo:** https://github.com/adamwahla1/openclaw-mission-control
**Branch:** `master`
**Project root:** `/data/users/LJTvWmv8w3YZfYb6dMwkwprDPJv1/Workspace/openclaw_mission_control`

This is the master handover document. It is intentionally exhaustive so another
AI / engineer can pick up the project cold. Read this first, then drill into
the supporting documents in this folder:

- [`01-architecture.md`](./01-architecture.md) — Stack, processes, data flow
- [`02-session-changes.md`](./02-session-changes.md) — Every file changed in this session, with code & rationale
- [`03-openclaw-bugs.md`](./03-openclaw-bugs.md) — OpenClaw bugs hit and the workarounds we landed
- [`04-local-gateway-setup.md`](./04-local-gateway-setup.md) — How to run a local OpenClaw v2026.4.25 gateway
- [`05-remote-gateway-vps.md`](./05-remote-gateway-vps.md) — Connecting MC to a remote (VPS) gateway, current pairing blocker
- [`06-settings-ui.md`](./06-settings-ui.md) — New Settings page, API endpoints, token resolution chain
- [`07-runbook.md`](./07-runbook.md) — Start/stop, health checks, common ops
- [`08-open-issues.md`](./08-open-issues.md) — Known issues and pending work
- [`09-this-session.md`](./09-this-session.md) — Current session: remote gateway fixes, token-only auth
- [`CHANGELOG.md`](../../CHANGELOG.md) — Complete feature history from day 1

---

## 1. What this project is

**OpenClaw Mission Control (MC)** is a dashboard that talks to an
**OpenClaw Gateway** (the agent runtime) over WebSocket and exposes a
React UI for orchestrating agents, sessions, debates, memory, the
"virtual office", autopilot pipelines, skills, and cost.

- **Frontend**: React 19 + Vite + TypeScript + Tailwind + shadcn/ui + Zustand
- **Backend**: FastAPI (Python) + SQLite (WAL)
- **Realtime**: Backend ↔ Gateway over WebSocket; Frontend ↔ Backend over SSE
- **AI access**: All model calls go through the OpenClaw Gateway (no direct
  provider SDKs in MC).
- **Backend role on the gateway**: `operator` WebSocket client with
  `operator.admin` scope, authenticated via Ed25519 device identity.

Phases already implemented (prior sessions):
1. Phase 1 — Foundation + Tasks
2. Phase 2 — Projects + Debate
3. Phase 3 — Memory Neural Map + Virtual Office
4. Phase 4 — Autopilot, Skills Hub, Security (Aegis), Cost Dashboard

---

## 2. What we did **in this session** (TL;DR)

We made MC work standalone, against either a **local** or **remote**
OpenClaw gateway, and added a real Settings UI to switch between them.

1. **Remote gateway support** — MC can now connect to any reachable
   OpenClaw gateway over WSS by configuring a URL + token. Token is sent
   in the WS URL query string (matching the pattern in the reference
   `crshdn/mission-control` repo).
2. **Standalone device identity** — MC keeps its Ed25519 keypair and
   device record under `~/.mission-control/identity/` instead of piggy-
   backing on `~/.openclaw/`. So MC works without any local OpenClaw
   install.
3. **Persistent gateway settings** — URL/token persisted at
   `~/.mission-control/gateway.json` and overridable via
   `MC_GATEWAY_URL` / `MC_GATEWAY_TOKEN` (or `OPENCLAW_*` aliases).
4. **Settings UI** — `frontend/src/pages/Settings.tsx` is now a real
   page: live status, URL/token inputs, Save & Reconnect, Reconnect,
   token preview, source indicator (env / persisted / auto), quick setup
   guide. Backed by new `GET/PUT /api/gateway/settings` endpoints.
5. **Local gateway auto-start** — `start.sh` now boots OpenClaw
   v2026.4.25 with a fresh sandbox config, the `pricing.bootstrap: false`
   workaround, bonjour disabled, and `--allow-unconfigured --verbose`.
   Works around the v2026.4.24 CPU-spin bug we hit earlier.
6. **VPS connection tested** against
   `wss://openclaw-npt3.srv1624328.hstgr.cloud` — handshake +
   signature succeed, gateway returns `DEVICE_PAIRING_REQUIRED`. This
   is expected behaviour — the device must be approved on the gateway
   side before it can connect.

## 3. What we did in the **2026-05-07 session**

Fixed remote gateway connection for atomicbot.ai hosted OpenClaw.

**Problem:** MC connected to `wss://7e4b2041f4.atomicbot.ai` but the gateway
kept closing with `DEVICE_PAIRING_REQUIRED` (1008 policy violation). The
user had no way to approve the pairing on the hosted gateway.

**Root cause:** MC was using the full Ed25519 device-auth handshake (v3
protocol with signed connect message). This requires device pairing approval
on the gateway. But the atomicbot.ai gateway uses **token-only auth** —
clients just send `auth: {token: "..."}` in the connect payload, no
signature needed.

**Fixes:**
1. `gateway_bridge.py` — auto-convert `https://` URLs to `wss://` for
   WebSocket compatibility.
2. `gateway_bridge.py` — detect local vs remote gateway. Remote gateways
   use token-only connect (simple `auth: {token}` payload). Local gateways
   still use full Ed25519 device auth for security.
3. `start.sh` — detect persisted remote gateway config and skip the 60s
   local OpenClaw gateway bootstrap (eliminates startup delay).

**Current state:**
- ✅ Connected and authenticated to `wss://7e4b2041f4.atomicbot.ai`
- ✅ `health` and `status` RPCs work
- ⚠️ `agents.list`, `channels.status`, and other operator methods fail
  with `"missing scope: operator.read"` — the token has **no scopes**.
  This is a **gateway-side configuration issue** (not MC code).
  The user needs to add `operator.read` (and ideally `operator.write`,
  `operator.admin`) scopes to the token via their atomicbot.ai control
  panel or OpenClaw CLI on the host.

See [`09-this-session.md`](./09-this-session.md) for full details,
including testing scripts and handoff checklist.

---

Verified working state at end of **2026-04-28** session:

```
GET /health
{"status":"ok",
 "gateway_connected":true,
 "gateway_authenticated":true,
 "auth_status":"authenticated",
 "version":"0.1.0"}

GET /api/gateway/agents
[{"id":"main","workspace":"/tmp/oc-home/.openclaw/workspace"}]
```

---

## 3. Key files touched in this session

| File | Change |
| --- | --- |
| `backend/config.py` | Added `MC_GATEWAY_URL/TOKEN` + `OPENCLAW_GATEWAY_URL/TOKEN` env vars; `save_gateway_settings()` / `load_gateway_settings()` persisting to `~/.mission-control/gateway.json`; resolution priority env → persisted → local autodetect. |
| `backend/services/device_auth.py` | New `MC_IDENTITY_DIR = ~/.mission-control/identity`. Identity load/save uses MC path first, OC path as fallback. `get_gateway_url/token()` now read from `config.settings`. |
| `backend/services/gateway_bridge.py` | `_build_ws_url()` appends `?token=…` to the WS URL. Scopes raised to `["operator.admin"]`. `update_gateway_settings()` for runtime reconfig. |
| `backend/routers/gateway.py` | New `GET /api/gateway/settings` and `PUT /api/gateway/settings`. |
| `frontend/src/pages/Settings.tsx` | Full Settings page (status, inputs, save/reconnect, setup guide). |
| `start.sh` | Auto-installs/locates OpenClaw v2026.4.25 (`.oc-v25/` then `.openclaw-install/`), creates `/tmp/oc-home/.openclaw/openclaw.json`, generates a token if missing, runs gateway with `--allow-unconfigured --verbose`. Waits up to 60s for it to come up. |
| `tasks.json` | Updated phase task statuses. |

Full code snippets and rationale: see [`02-session-changes.md`](./02-session-changes.md).

---

## 4. How it works end-to-end (current state)

1. `start.sh` is the single entry point.
2. It launches a local OpenClaw v2026.4.25 gateway (port 18789 by
   default) — unless the user overrides `MC_GATEWAY_URL` to point at a
   remote gateway, in which case the local one isn't strictly needed.
3. FastAPI backend boots on `$APP_PORT` (3000–3099 range).
4. On boot, `gateway_bridge` reads `settings.gateway_url/token` (env →
   persisted → autodetected from `~/.openclaw/openclaw.json`) and opens
   a WebSocket to `<url>?token=<token>`.
5. MC presents a device challenge / signature handshake using the
   Ed25519 key in `~/.mission-control/identity/device.json`.
6. Gateway either replies `AUTHENTICATED` (local, allow-unconfigured) or
   `DEVICE_PAIRING_REQUIRED` (VPS, awaiting approval).
7. Frontend at `/settings` lets the user change URL/token at runtime —
   PUT triggers `gateway_bridge.update_gateway_settings()` which closes
   the current WS, persists, and lets the supervisor reconnect.

Detailed sequence diagram and component map in
[`01-architecture.md`](./01-architecture.md).

---

## 5. Outstanding issues

These are **not blockers for code review** but are pending real-world ops:

1. **VPS device pairing** — The VPS gateway returned
   `DEVICE_PAIRING_REQUIRED`. The user must run an "approve device"
   action on the VPS (either via the VPS's own MC UI or `openclaw`
   CLI). Until then MC connects but can't do work against the VPS.
2. **No model providers configured** — The local gateway has no
   OpenRouter / Kimi / Anthropic key yet, so `agent.run` will fail
   with "no provider". Add via `openclaw configure` or write keys into
   `~/.openclaw/openclaw.json` `providers` block. (Out of scope for MC
   itself — this is gateway config.)
3. **`chokidar` missing for memory-core plugin** — Non-fatal warning at
   gateway startup. Doesn't affect MC. Workaround: `npm i -g chokidar`
   in the OpenClaw install dir, or ignore.
4. **Bonjour/mDNS plugin** — Crashes the gateway in the sandbox. We set
   `OPENCLAW_DISABLE_BONJOUR=1` in `start.sh`. If you change the start
   script, keep that.
5. **Auth status surfacing** — When the gateway returns
   `DEVICE_PAIRING_REQUIRED`, `auth_status` becomes `pairing_required`.
   The Settings page shows it but there's no "Approve on gateway" button
   yet — that requires a paired-device approval API on the gateway side.

Full list with reproduction details in [`08-open-issues.md`](./08-open-issues.md).

---

## 6. How to run it (quick)

```bash
cd /data/users/LJTvWmv8w3YZfYb6dMwkwprDPJv1/Workspace/openclaw_mission_control
./start.sh
```

That will:
- Locate / install OpenClaw v2026.4.25
- Boot the gateway on port 18789 (logs in `/tmp/openclaw-gateway.log`)
- Boot the FastAPI backend on `$APP_PORT`
- Frontend is served as static assets by the backend (already built into
  `frontend/dist/`).

To point at a remote gateway instead:

```bash
export MC_GATEWAY_URL="wss://your-gateway.example.com"
export MC_GATEWAY_TOKEN="your-token"
./start.sh
# then open /settings in MC and approve / pair the device on the gateway
```

Full runbook in [`07-runbook.md`](./07-runbook.md).

---

## 7. Where to look when things go wrong

- **Backend ↔ Gateway issues**: `backend/services/gateway_bridge.py`,
  log line "GatewayBridge:" prefix.
- **Auth / signing issues**: `backend/services/device_auth.py`. Identity
  files at `~/.mission-control/identity/`.
- **Settings persistence**: `~/.mission-control/gateway.json`.
- **Local gateway logs**: `/tmp/openclaw-gateway.log`.
- **Local gateway home**: `/tmp/oc-home/.openclaw/`.
- **Gateway port**: 18789 (configured in `start.sh`).
- **MC port**: `$APP_PORT` (3000–3099, picked by sandbox).

---

See the supporting documents in this folder for everything else.
