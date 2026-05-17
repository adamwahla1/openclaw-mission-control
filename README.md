# Mission Control

> A local-first, supervised AI agent command center with a native runtime,
> OpenRouter provider support, durable run timelines, approvals, and optional
> OpenClaw adapter support.

Mission Control started as an OpenClaw dashboard. The current direction is
different: Mission Control is becoming its own native agent runtime. OpenClaw
is now optional integration context, not the default dependency.

---

## Current Status

Native runtime readiness is implemented on:

```text
branch: native-runtime-readiness
PR: https://github.com/adamwahla1/openclaw-mission-control/pull/1
```

Prototype capabilities:

- Boots in native runtime mode without requiring OpenClaw.
- Stores native runtime config in SQLite.
- Supports provider configuration with OpenRouter as the first provider.
- Supports model defaults by purpose.
- Creates native agents and sessions.
- Starts Project Builder runs.
- Persists run events.
- Shows run timeline in the UI.
- Pauses for human approval on write-risk work.
- Resumes or cancels based on approval decision.
- Stores final report artifacts.
- Keeps OpenClaw as an optional adapter path.

Important verification note:

- Backend syntax checks passed.
- Frontend build passed.
- Browser workflow was tested with real OpenRouter model output through a
  prototype API harness.
- The real FastAPI backend still needs one clean end-to-end browser test in a
  fully installed environment.

---

## Quick Start

From the repo root:

```bash
./start.sh
```

Common local URLs:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:3100`

Then:

1. Open `/settings`.
2. Keep runtime set to `native`.
3. Configure OpenRouter.
4. Test the provider key.
5. Open `/runs`.
6. Start a Project Builder run.
7. Approve the pending action.
8. Read the final report.

Do not commit or document real API keys.

---

## What Mission Control Is Becoming

Mission Control is intended to be a supervised Project Builder and multi-agent
runtime.

Core concepts:

- Agents
- Sessions
- Messages
- Runs
- Run steps
- Run events
- Artifacts
- Approvals
- Providers
- Model configs
- Tool registry
- Cost records
- Memory

The UI should be built around those Mission Control concepts, not around
provider-specific or runtime-specific details.

---

## Architecture

```text
Browser UI
  |
  | HTTP + SSE
  v
FastAPI backend
  |
  +-- RuntimeRegistry
  |     |
  |     +-- NativeMissionControlRuntime   default
  |     |
  |     +-- OpenClawRuntimeAdapter        optional
  |
  +-- Provider layer
  |     |
  |     +-- OpenRouterProvider            first provider
  |
  +-- SQLite
        |
        +-- agents, tasks, projects, memory, cost
        +-- runtime/provider/model config
        +-- sessions, messages, runs, events, artifacts, approvals, tools
```

Frontend:

- React 19
- Vite
- TypeScript
- Tailwind CSS
- shadcn/ui style components

Backend:

- FastAPI
- Python 3.11+
- SQLite WAL
- Pydantic validation

Runtime direction:

- Native runtime first.
- Pydantic AI for typed single-agent execution.
- LangGraph for durable multi-step workflows.
- OpenRouter first provider.
- OpenClaw optional adapter.

---

## Main Pages

| Page | Purpose |
| --- | --- |
| Dashboard | Overview. Some copy may still need native-runtime cleanup. |
| Agents | Mission Control-owned agents. |
| Tasks | Kanban/task workflow. Dispatch should start native Project Builder runs. |
| Runs | Native runtime lab: start Project Builder, inspect events, approve work. |
| Settings | Runtime, providers, models, tools, approvals, recent runs. |
| Cost | Usage/cost reporting. Needs more native cost validation. |
| Memory | Mission Control memory views. |
| Debate | Existing debate UI, future migration target for native runtime. |
| Autopilot | Existing automation UI, future migration target for native runtime. |

---

## Native API Quick Reference

Runtime:

```bash
curl http://localhost:3100/api/runtime/status
```

Providers:

```bash
curl http://localhost:3100/api/providers
```

OpenRouter key test:

```bash
curl -X POST http://localhost:3100/api/providers/openrouter/test \
  -H "Content-Type: application/json" \
  -d '{"api_key":"sk-or-v1-REPLACE_ME"}'
```

Runs:

```bash
curl -X POST http://localhost:3100/api/runs \
  -H "Content-Type: application/json" \
  -d '{"kind":"project_builder","title":"Test run","input":"Plan a tiny feature."}'
```

Events:

```bash
curl http://localhost:3100/api/runs/RUN_ID/events
```

Approvals:

```bash
curl http://localhost:3100/api/approvals
```

Tools:

```bash
curl http://localhost:3100/api/tools
```

---

## Project Structure

```text
openclaw-mission-control/
|-- backend/
|   |-- main.py
|   |-- routers/
|   |   |-- runtime.py
|   |   |-- providers.py
|   |   |-- runs.py
|   |   |-- approvals.py
|   |   |-- tools.py
|   |   |-- agents.py
|   |   |-- orchestrator.py
|   |   |-- gateway.py              legacy/optional OpenClaw routes
|   |
|   |-- services/
|       |-- native_schema.py
|       |-- runtime_registry.py
|       |-- native_runtime.py
|       |-- providers.py
|       |-- ai_client.py
|       |-- orchestrator.py
|       |-- agent_factory.py
|       |-- gateway_bridge.py       legacy/optional OpenClaw bridge
|
|-- frontend/
|   |-- src/
|       |-- pages/
|           |-- Settings.tsx
|           |-- Runs.tsx
|       |-- components/
|       |-- hooks/
|
|-- docs/handover/
|-- CHANGELOG.md
|-- start.sh
```

---

## OpenClaw Status

OpenClaw is not the default runtime anymore.

OpenClaw-related code remains because it may be useful as an optional adapter:

- `backend/services/gateway_bridge.py`
- `backend/services/device_auth.py`
- `backend/routers/gateway.py`
- legacy handover files about gateway setup

Do not build new core features that require OpenClaw unless the user explicitly
changes direction.

---

## Development Verification

Backend syntax check example:

```bash
python -m py_compile backend/main.py backend/services/native_runtime.py
```

Frontend build:

```bash
cd frontend
npm install
npm run build
```

Expected:

- Build should succeed.
- Chunk-size warnings are acceptable for now.

---

## Known Gaps

Highest priority:

- Real FastAPI end-to-end browser test.
- Replace stale OpenClaw wording in Dashboard.
- Implement real Pydantic AI typed agent calls.
- Implement real LangGraph Project Builder workflow.
- Add real supervised repository tools.
- Add durable SSE replay behavior.
- Harden provider key storage.
- Add tests.

See `docs/handover/08-open-issues.md` for details.

---

## Handover Docs

Start here:

```text
docs/handover/HANDOVER.md
```

The handover docs are intentionally detailed. They are written so another
engineer or AI model can continue the project without relying on conversation
memory.

---

## License

MIT License - Copyright (c) 2026 Adam Wahla.

