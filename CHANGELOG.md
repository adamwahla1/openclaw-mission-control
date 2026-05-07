# OpenClaw Mission Control — Changelog

> Complete feature history from initial scaffold through all build phases.
> Each commit maps to a concrete set of deliverables.

---

## Phase 1 — Foundation + Tasks

### `3c506d2` Phase 1A: Foundation scaffold
- FastAPI backend with SQLite (WAL mode) database
- SQLAlchemy models for tasks, projects, agents
- Pydantic schemas for API validation
- React 19 + Vite + TypeScript + Tailwind CSS + shadcn/ui frontend scaffold
- Zustand store for global state
- Basic routing and layout shell
- `start.sh` launcher script

### `f24293b` Phase 1B: Kanban board, Orchestrator, Agent Factory, Live View
- **Task Board** (`TaskBoard.tsx`) — drag-and-drop Kanban with columns:
  - Backlog, In Progress, Review, Done
  - Task creation, editing, priority assignment, assignee selection
- **Orchestrator** (`orchestrator.py`) — task distribution engine
  - Auto-assigns tasks to agents based on skills and load
  - Task status transitions and notifications
- **Agent Factory** (`agent_factory.py`) — intelligent agent creation
  - Research → SOUL construction → skill injection → validation pipeline
  - Personality and expertise configuration
- **Live View** — real-time task and agent status display
- Backend routers: `tasks.py`, `agents.py`, `orchestrator.py`

### `5922b9a` Add final report generation and Report tab in task drawer
- Report generation for completed tasks
- Report tab in task detail drawer UI
- Activity log and summary export

### `99428c9` Task-specific simulation reports and activity messages
- Simulation report generation per task
- Rich activity messages with markdown rendering
- Task context awareness in reports

### `3b2b424` Fix Vite proxy port — use APP_PORT env var for correct backend routing
- Fixed Vite dev server proxy to use `$APP_PORT` env var
- Ensured backend port is `$APP_PORT + 100` consistently
- Critical fix for sandbox deployment where ports are dynamically allocated

---

## Phase 2 — Projects + Debate

### `9e09c54` Phase 2: Smart Projects + Debate Room
- **Projects** (`Projects.tsx`, `ProjectDetail.tsx`)
  - Project creation with description, goals, timeline
  - Project-agent assignment and tracking
  - Project status dashboard
- **Debate Room** (`DebateRoom.tsx`)
  - Multi-agent debate orchestration
  - Proponent vs opponent agent roles
  - Round-based debate flow with rebuttals

### `c705eb8` AI-powered debates: Gemini-driven expert agents with multi-turn context
- Gemini integration for debate agent intelligence
- Multi-turn context preservation across debate rounds
- Expert agent specialization (researcher, analyst, critic)
- Debate quality scoring and consensus detection
- Backend: `debates.py` router, `debate_engine.py` service

---

## Phase 3 — Memory + Office

### `3bef51b` Phase 3: Memory Neural Map + Virtual Office
- **Memory Neural Map** (`MemoryMap.tsx`)
  - D3.js force-directed graph visualization
  - Memory nodes with relationships and strength weights
  - Interactive zoom, pan, and node inspection
  - Memory search and filtering
- **Virtual Office** (`VirtualOffice.tsx`)
  - Isomorphic 2D office visualization on HTML5 Canvas
  - Agent avatars positioned in office space
  - Real-time agent presence and activity indicators
  - Office navigation and room-based grouping
- Backend: `memories.py`, `office.py` routers
- Services: memory indexing, office state management

---

## Phase 4 — Autopilot + Skills + Security + Cost

### `834511c` Phase 4: Autopilot pipeline, Skills Hub, Security Audit (Aegis), Cost Dashboard
- **Autopilot** (`Autopilot.tsx`)
  - Pipeline definition and execution
  - Step-by-step automation workflows
  - Agent-triggered pipeline runs
- **Skills Hub** (`SkillsHub.tsx`)
  - Skill catalog browsing and installation
  - Skill version management
- **Security Audit / Aegis** (`SecurityAudit.tsx`)
  - Security rule packs and scanning
  - Vulnerability detection across agents and configurations
  - Audit report generation
- **Cost Dashboard** (`CostDashboard.tsx`)
  - Cost tracking per agent, per session, per project
  - Usage metrics and budget alerts
  - Provider cost breakdown
- Backend routers: `autopilot.py`, `skills.py`, `security.py`, `costs.py`
- Services: `autopilot_engine.py`, `aegis.py`, `cost_tracker.py`

### `32ff368` Skills Hub: live registry integration with skills.sh, Skills Directory, Anthropic, Hugging Face
- Live skill registry integration (`skills.sh` / `registry_client.py`)
- Skills Directory with search and categories
- Anthropic and Hugging Face skill pack support
- Skill installation from remote registries
- Skill dependency resolution

---

## Gateway Integration + Device Auth

### `d58e26c` Implement OpenClaw device auth protocol with Ed25519 signing
- **Device Authentication Protocol** (`device_auth.py`)
  - Ed25519 keypair generation and persistence
  - Challenge-response handshake with OpenClaw Gateway
  - v2 and v3 signature payload construction
  - Device identity stored in `~/.mission-control/identity/`
- **Gateway Bridge** (`gateway_bridge.py`)
  - Persistent WebSocket connection to OpenClaw Gateway
  - Auto-reconnect with exponential backoff
  - Bidirectional event bridging (gateway → SSE → frontend)
  - RPC convenience methods for all gateway operations
- Backend router: `events.py` — SSE broadcaster for real-time frontend updates

### `4f4df47` Add Render deployment config, fix TS build errors, serve static frontend from backend
- `render.yaml` deployment blueprint for Render.com
- TypeScript build errors fixed across frontend
- Backend serves static `frontend/dist/` when deployed
- Production build pipeline: `npm run build` → FastAPI `StaticFiles`

### `a122f21` Remote/local gateway support, Settings UI, standalone identity, v2026.4.25 auto-start
- **Settings UI** (`Settings.tsx`)
  - Gateway URL and token configuration form
  - Connection status diagnostics display
  - Device identity info panel
  - "Save & Reconnect" action
- **Gateway configuration priority chain** (`config.py`)
  1. `MC_GATEWAY_URL` / `MC_GATEWAY_TOKEN` env vars
  2. `OPENCLAW_GATEWAY_URL` / `OPENCLAW_GATEWAY_TOKEN` env vars
  3. Persisted file at `~/.mission-control/gateway.json`
  4. Auto-detected from `~/.openclaw/openclaw.json`
  5. Default `ws://127.0.0.1:18789`
- **Local gateway auto-start** (`start.sh`)
  - Detects OpenClaw CLI v2026.4.25
  - Generates minimal gateway config with `pricing.bootstrap: false`
  - Disables bonjour/mDNS (`OPENCLAW_DISABLE_BONJOUR=1`)
  - Boots gateway on port 18789 with `--allow-unconfigured --verbose`
  - Waits up to 60s for gateway readiness
- Standalone identity: MC maintains its own device keypair independent of local OpenClaw install

### `054fbd1` Wire gatewayConnected to live status via useGatewayStatus hook (polls + SSE)
- `useGatewayStatus.ts` frontend hook
  - Polls `/api/gateway/status` every 5 seconds
  - Listens to SSE `gateway` events for real-time updates
  - Provides `connected`, `authenticated`, `authStatus`, `serverInfo`
- Gateway status badge in app header
- Settings page shows live diagnostics

### `b01f5da` Fix remote gateway connection: token-only auth for remote, skip local gateway when remote configured
- **Auto-convert https→wss** in `gateway_bridge.py::_get_gateway_url()`
  - `https://` URLs converted to `wss://` for WebSocket compatibility
  - `http://` URLs converted to `ws://`
- **Token-only auth for remote gateways**
  - Remote gateways (non-localhost) use simple `auth: {token: ...}` connect
  - Avoids `DEVICE_PAIRING_REQUIRED` rejection that occurs with Ed25519 device auth on shared/token-only gateways
  - Local gateways still use full Ed25519 signature handshake
- **Skip local gateway bootstrap when remote configured** (`start.sh`)
  - Detects persisted remote gateway config in `~/.mission-control/gateway.json`
  - Skips the 60-second local OpenClaw gateway wait when a remote URL is configured
  - Eliminates startup delay for remote-only deployments

---

## Documentation

### `d465219` Add comprehensive README with quick start, architecture, API reference, and handover index
- Full README.md with architecture diagrams
- API endpoint reference
- Troubleshooting matrix
- Handover document index
- Deployment instructions (Render.com)

### Handover documents (`docs/handover/`)
- `01-architecture.md` — Stack, processes, data flow, module tree
- `02-session-changes.md` — File-by-file code changes with rationale
- `03-openclaw-bugs.md` — OpenClaw bugs hit and workarounds
- `04-local-gateway-setup.md` — How to run OC v2026.4.25 locally
- `05-remote-gateway-vps.md` — Connecting MC to a remote gateway
- `06-settings-ui.md` — Settings page API + token resolution chain
- `07-runbook.md` — Start/stop, health checks, common ops
- `08-open-issues.md` — Known issues and pending work
- `09-this-session.md` — Current session context (updated each session)

---

## Feature Summary by Area

| Area | Features | Backend | Frontend |
|------|----------|---------|----------|
| **Tasks** | Kanban board, drag-and-drop, priority, assignees, reports | `tasks.py`, `orchestrator.py` | `TaskBoard.tsx` |
| **Agents** | Agent factory, SOUL construction, skills, trust score | `agents.py`, `agent_factory.py` | Dashboard |
| **Projects** | Project management, agent assignment, timelines | `projects.py` | `Projects.tsx`, `ProjectDetail.tsx` |
| **Debates** | Multi-agent debates, Gemini-driven, multi-turn | `debates.py`, `debate_engine.py` | `DebateRoom.tsx` |
| **Memory** | D3.js neural graph, memory relationships | `memories.py` | `MemoryMap.tsx` |
| **Office** | 2D Canvas virtual office, agent presence | `office.py` | `VirtualOffice.tsx` |
| **Autopilot** | Pipeline workflows, step execution | `autopilot.py`, `autopilot_engine.py` | `Autopilot.tsx` |
| **Skills** | Registry integration, install, directory | `skills.py`, `registry_client.py` | `SkillsHub.tsx` |
| **Security** | Aegis audit, rule packs, vulnerability scan | `security.py`, `aegis.py` | `SecurityAudit.tsx` |
| **Cost** | Usage tracking, budget alerts, provider breakdown | `costs.py`, `cost_tracker.py` | `CostDashboard.tsx` |
| **Gateway** | WS bridge, device auth, SSE events, Settings | `gateway.py`, `gateway_bridge.py`, `device_auth.py`, `events.py` | `Settings.tsx` |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite, TypeScript, Tailwind CSS, shadcn/ui, Zustand |
| Backend | FastAPI, Python 3.11, SQLAlchemy, SQLite (WAL mode) |
| Real-time | WebSocket (backend ↔ gateway), SSE (frontend ↔ backend) |
| Auth | Ed25519 device identity, token-based gateway auth |
| Viz | D3.js (memory graph), HTML5 Canvas (office) |
| AI | All calls routed through OpenClaw Gateway |
| Deploy | Render.com blueprint, static frontend served by FastAPI |
