# 01 - Native-First Architecture

This file explains the current architecture after the native runtime readiness
work. Older docs and old commit messages describe Mission Control as an
OpenClaw dashboard. That is now legacy context. The architecture is now:

```text
Browser UI
  |
  | HTTP + SSE
  v
FastAPI Mission Control backend
  |
  +-- RuntimeRegistry
  |     |
  |     +-- NativeMissionControlRuntime   <-- default
  |     |
  |     +-- OpenClawRuntimeAdapter        <-- optional, legacy integration
  |
  +-- Provider layer
  |     |
  |     +-- OpenRouterProvider            <-- first real provider
  |
  +-- SQLite ledger
        |
        +-- agents/tasks/projects/debates/memory/cost
        +-- runtime_config/provider_configs/model_configs
        +-- sessions/messages/runs/run_steps/run_events/artifacts/approvals/tools
```

The core rule is simple:

**Mission Control owns the product state. The runtime executes work. The
provider supplies model calls. OpenClaw is no longer the owner of the product.**

---

## 1. Process Map

Local development process:

```text
start.sh
  |
  +-- backend: FastAPI / uvicorn
  |
  +-- frontend: Vite dev server
  |
  +-- optional OpenClaw gateway only when active runtime is openclaw
```

Native mode does not require an OpenClaw process.

Production-style build:

```text
FastAPI backend
  |
  +-- serves API routes
  |
  +-- serves built frontend from frontend/dist
```

---

## 2. Ports

The old port model still exists for dev convenience:

| Service | Default |
| --- | --- |
| Frontend dev server | `APP_PORT`, commonly `3000` |
| FastAPI backend | `APP_PORT + 100`, commonly `3100` |
| Optional local OpenClaw gateway | `18789` |

In native mode, port `18789` is not needed.

---

## 3. Backend Module Map

Important backend files:

```text
backend/
|-- main.py
|   FastAPI app, lifespan startup, router mounting, static frontend serving.
|
|-- services/
|   |-- native_schema.py
|   |   Creates native runtime tables and seed rows.
|   |
|   |-- runtime_registry.py
|   |   Holds active runtime. Default is native.
|   |
|   |-- native_runtime.py
|   |   Implements local agents, sessions, messages, Project Builder runs,
|   |   persisted events, approvals, artifacts, and resume/cancel.
|   |
|   |-- providers.py
|   |   Defines ModelProvider abstraction and OpenRouterProvider.
|   |
|   |-- ai_client.py
|   |   Existing AI helper now routes through provider config when available.
|   |
|   |-- orchestrator.py
|   |   Native-first task dispatch. Creates native run instead of relying on
|   |   gateway execution.
|   |
|   |-- agent_factory.py
|   |   Native-first agent creation.
|   |
|   |-- gateway_bridge.py
|   |   Legacy/optional OpenClaw WebSocket client.
|   |
|   |-- db.py
|   |   SQLite connection helpers.
|   |
|   |-- sse.py
|       Backend-to-frontend event broadcaster.
|
|-- routers/
|   |-- runtime.py
|   |   /api/runtime/status and /api/runtime/active.
|   |
|   |-- providers.py
|   |   /api/providers and /api/model-configs.
|   |
|   |-- runs.py
|   |   /api/runs run creation, events, cancel, resume.
|   |
|   |-- approvals.py
|   |   /api/approvals approve/reject workflow.
|   |
|   |-- tools.py
|   |   /api/tools registry and policy updates.
|   |
|   |-- agents.py
|   |   Native-backed agents by default.
|   |
|   |-- orchestrator.py
|       Native-backed task dispatch/status.
```

---

## 4. Frontend Module Map

Important frontend files:

```text
frontend/src/
|-- App.tsx
|   Route registration. Adds /runs.
|
|-- hooks/useGatewayStatus.ts
|   Historical name, but now reads /api/runtime/status for sidebar status.
|
|-- components/layout/Sidebar.tsx
|   Adds Runs navigation and native runtime status wording.
|
|-- pages/Settings.tsx
|   Runtime, Providers, Models, Tools, Approvals, Recent Runs.
|
|-- pages/Runs.tsx
|   Project Builder prototype lab. Starts runs, displays timeline,
|   handles approvals, shows final report.
```

Known stale UI copy:

- Dashboard still contains old wording about connecting to OpenClaw Gateway.
  This should be replaced with native runtime language in the next cleanup.

---

## 5. Runtime Registry

`backend/services/runtime_registry.py` owns the active runtime.

It exists so Mission Control can speak to one runtime interface while hiding
implementation details. Today there are two runtime concepts:

- `native`
  - Default.
  - Runs in Mission Control backend.
  - Owns runs, events, approvals, and artifacts.

- `openclaw`
  - Optional adapter.
  - Uses the existing OpenClaw gateway bridge.
  - Should not start unless explicitly selected.

Expected behavior:

1. App starts.
2. Native schema is ensured.
3. Runtime registry starts.
4. Active runtime is read from `runtime_config`.
5. If active runtime is `native`, no OpenClaw connection is required.
6. If active runtime is `openclaw`, the adapter starts the gateway bridge.

---

## 6. Provider Layer

`backend/services/providers.py` defines the provider abstraction.

Core interface:

```text
ModelProvider
  list_models()
  test()
  chat()
  stream_chat()
  estimate_cost()
  get_usage()
```

First implementation:

```text
OpenRouterProvider
```

OpenRouter is useful as the first provider because it gives one API surface
for many models. It supports model lists, chat completions, routing policies,
streaming-style usage in many cases, tool-calling on supported models, and
usage metadata.

Provider configuration lives in `provider_configs`.

Model purpose configuration lives in `model_configs`.

Seeded purposes:

- `planner`
- `builder`
- `reviewer`
- `cheap_fast`
- `long_context`

The purpose of model configs is to avoid hard-coding one model everywhere.
For example, Project Builder can use a stronger model for planning and a
cheaper model for quick summarization.

---

## 7. Native Database Concepts

The native schema is created by `ensure_native_runtime_schema(db)`.

Important tables:

| Table | Purpose |
| --- | --- |
| `runtime_config` | Stores active runtime, default `native`. |
| `provider_configs` | Stores provider settings such as OpenRouter key. |
| `model_configs` | Stores model defaults by purpose. |
| `sessions` | Native conversation/session records. |
| `messages` | User/assistant/system messages in sessions. |
| `runs` | Durable execution records for Project Builder and future workflows. |
| `run_steps` | Named phases within a run. |
| `run_events` | Append-only event ledger. UI truth source. |
| `artifacts` | Final reports, generated files, patch drafts, summaries. |
| `approvals` | Human approval/rejection records. |
| `tool_registry` | Available tools, risk levels, approval modes. |

Existing tables still matter:

- `agents`
- `tasks`
- `projects`
- `debates`
- `memories`
- `cost_records`

Those are now Mission Control-owned tables. They are not merely gateway mirrors.

---

## 8. Run Event Flow

The run event ledger is the most important new architecture concept.

Flow:

```text
User starts Project Builder
  |
  v
POST /api/runs
  |
  v
NativeMissionControlRuntime.start_run()
  |
  +-- insert row in runs
  +-- emit run.started
  +-- emit step.started / model.output / step.completed events
  +-- create approval if needed
  +-- emit approval.required
  +-- pause run
```

When approved:

```text
User clicks Approve
  |
  v
POST /api/approvals/{id}/approve
  |
  v
NativeMissionControlRuntime.resume_run()
  |
  +-- emit approval.approved
  +-- continue review/test/report
  +-- save artifact
  +-- emit run.completed
```

The UI should treat `run_events` as the truth source. If a browser refreshes,
it can reload events from:

```text
GET /api/runs/{run_id}/events
```

The eventual goal is live SSE plus replay from persisted events.

---

## 9. Supervised Tool Model

Tools are registered with:

- name
- description
- schema
- risk level
- approval mode
- enabled flag

Seeded tools:

- `repo.read` - read-only
- `repo.search` - read-only
- `repo.draft_patch` - write risk
- `tests.run` - write/execution risk depending on command
- `report.summarize` - read-only

Risk levels used in planning:

- `read-only`
- `write`
- `destructive`
- `external`
- `financial`

Default product posture:

**Supervised by default.** Read-only tools may run automatically. Write,
destructive, external, and financial tools should pause for approval unless
the user explicitly changes policy.

---

## 10. OpenClaw Adapter Position

OpenClaw files remain in the repo:

- `backend/services/gateway_bridge.py`
- `backend/services/device_auth.py`
- `backend/routers/gateway.py`
- old gateway settings logic

Do not delete them casually. They may become a useful optional adapter.

But do not build new product features assuming OpenClaw is present.

Correct direction:

```text
UI -> Mission Control runtime interface -> native runtime by default
                                    |
                                    +-> optional OpenClaw adapter later
```

Incorrect direction:

```text
UI -> OpenClaw gateway -> agents/runs/tools
```

