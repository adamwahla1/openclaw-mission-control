# 02 - Native Runtime Readiness Changes

This document explains what changed in the native runtime readiness branch.
It is written as a handover for someone who has not seen the planning
conversation.

The branch goal was not to finish the final AI runtime. The goal was to make
Mission Control boot and operate without OpenClaw, then add the foundations
needed for a real native runtime.

---

## 1. Product Direction Change

Old direction:

```text
Mission Control is a dashboard for OpenClaw Gateway.
OpenClaw owns agent execution.
Mission Control mirrors gateway state.
```

New direction:

```text
Mission Control is its own local-first agent command center.
Mission Control owns agents, runs, events, approvals, tools, memory, and cost.
OpenClaw is optional.
```

This is why so many changes touch runtime status, agents, settings, providers,
runs, approvals, and the orchestrator.

---

## 2. Backend Files Changed

### `backend/main.py`

Purpose:

- Make app startup native-runtime-aware.
- Mount new routers.
- Stop treating gateway startup as the central app behavior.

Important changes:

- App title changed toward Mission Control rather than OpenClaw-only wording.
- Startup calls `ensure_native_runtime_schema(db)`.
- Startup starts `runtime_registry`.
- OpenClaw starts only when active runtime is `openclaw`.
- New routers mounted:
  - `runtime`
  - `providers`
  - `runs`
  - `approvals`
  - `tools`
- `/api/health` now reports native runtime fields:
  - `runtime_ready`
  - `active_runtime`
  - compatibility gateway fields for older UI/code

Why this matters:

The backend can now start even when no OpenClaw gateway exists.

---

### `backend/services/native_schema.py`

Purpose:

- Create the database foundation for the native runtime.

Creates these tables if missing:

- `runtime_config`
- `provider_configs`
- `model_configs`
- `sessions`
- `messages`
- `runs`
- `run_steps`
- `run_events`
- `artifacts`
- `tool_registry`

Extends existing `approvals` table with:

- `run_id`
- `tool_name`
- `risk_level`
- `request_payload`
- `decision_payload`

Seeds:

- active runtime = `native`
- model purposes:
  - `planner`
  - `builder`
  - `reviewer`
  - `cheap_fast`
  - `long_context`
- tool registry:
  - `repo.read`
  - `repo.search`
  - `repo.draft_patch`
  - `tests.run`
  - `report.summarize`

Why this matters:

The database now has durable places to put run state, timeline events, provider
settings, model defaults, approval decisions, and artifacts.

---

### `backend/services/runtime_registry.py`

Purpose:

- Provide one runtime selector for the backend.

Concepts:

- `native` is the default runtime.
- `openclaw` is an optional adapter.
- Runtime changes are stored in `runtime_config`.

Important behavior:

- `set_active("native")` stops OpenClaw adapter behavior.
- `set_active("openclaw")` starts the OpenClaw adapter.
- `status()` exposes active runtime and readiness.

Why this matters:

The rest of the app can ask for "the runtime" without caring which engine is
behind it.

---

### `backend/services/native_runtime.py`

Purpose:

- Implement the first native Mission Control runtime.

Main methods:

- `status`
- `list_agents`
- `create_agent`
- `get_agent`
- `start_session`
- `get_session`
- `send_message`
- `start_run`
- `get_run`
- `list_runs`
- `get_events`
- `cancel_run`
- `resume_run`

Project Builder v1 flow:

1. `intake`
2. `plan`
3. `research`
4. `build_draft`
5. approval pause
6. `review`
7. `test_plan`
8. `report`

Important event behavior:

- Inserts rows into `run_events`.
- Broadcasts events to SSE.
- Stores final report as an artifact.
- Updates linked task to `review` when appropriate.

Provider behavior:

- If OpenRouter is configured, model calls go through provider layer.
- If no provider is configured, fallback text is used so the UI can still
  demonstrate flow.

Approval behavior:

- A write-risk draft patch step creates an approval.
- Run pauses with status `waiting_approval`.
- Approval resumes the run.
- Rejection cancels the run.

Important limitation:

Pydantic AI and LangGraph are only lightly integrated at readiness level.
The file imports/checks availability, but the deep final runtime still needs
to be built.

---

### `backend/services/providers.py`

Purpose:

- Add provider abstraction and OpenRouter implementation.

Core classes/concepts:

- `ModelProvider`
- `ProviderResponse`
- `OpenRouterProvider`

Provider operations:

- `list_models`
- `test`
- `chat`
- `stream_chat`
- `estimate_cost`
- `get_usage`

Config helpers:

- `get_provider_config`
- `upsert_provider_config`
- `redact_provider_config`
- `get_model_config`
- `record_provider_cost`

Routing policies:

- `auto`
- `cheap`
- `fast`
- `strong`
- `pinned`

Cost fields added/used:

- `provider`
- `requested_model`
- `actual_model`
- `latency_ms`
- `native_run_id`

Why `native_run_id` exists:

The old `cost_records.run_id` had compatibility assumptions tied to autopilot
runs. `native_run_id` avoids breaking old foreign key expectations while
allowing costs to point to native runs.

---

### `backend/services/ai_client.py`

Purpose:

- Stop being Gemini-first.
- Route through the provider layer when provider config exists.

Current behavior:

1. If OpenRouter is configured, use OpenRouter provider.
2. Else if old Gemini env config exists, use Gemini fallback.
3. Else return offline placeholder output.

Why this matters:

Existing debates/autopilot-style features can begin migrating toward the same
provider layer without one big rewrite.

---

### `backend/services/agent_factory.py`

Purpose:

- Make agent creation native-first.

Important changes:

- Creates Mission Control-owned agents.
- Does not require active gateway registration.
- Leaves `gateway_agent_id` empty/null for native agents.
- System prompt describes Mission Control native supervised runtime.

---

### `backend/services/orchestrator.py`

Purpose:

- Make task dispatch create native Project Builder runs.

Flow:

1. Load task.
2. Mark task assigned/in progress.
3. Decompose if needed.
4. Create or select native agent.
5. Start native session.
6. Start `project_builder` run.
7. Store native run id in compatibility field where old UI expects session id.
8. Broadcast task/run events.

Important compatibility note:

`tasks.gateway_session_id` may contain a native run id. The name is old. Treat
it as "external or execution reference" until schema naming is cleaned.

---

### `backend/routers/runtime.py`

New routes:

- `GET /api/runtime/status`
- `PUT /api/runtime/active`

Purpose:

- Let UI read active runtime.
- Let UI switch between native and optional OpenClaw.

---

### `backend/routers/providers.py`

New routes:

- `GET /api/providers`
- `POST /api/providers`
- `POST /api/providers/openrouter/test`
- `GET /api/providers/openrouter/models`
- `GET /api/model-configs`
- `POST /api/model-configs`

Purpose:

- Configure OpenRouter.
- Test key.
- Discover models.
- Save model defaults by purpose.

Security note:

API keys must be redacted in responses. Do not return full provider secrets.

---

### `backend/routers/runs.py`

New routes:

- `GET /api/runs`
- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `POST /api/runs/{run_id}/cancel`
- `POST /api/runs/{run_id}/resume`

Purpose:

- Start and inspect native runs.
- Replay event timeline.
- Cancel or resume runs.

---

### `backend/routers/approvals.py`

New/updated routes:

- `GET /api/approvals`
- `POST /api/approvals`
- `POST /api/approvals/{id}/approve`
- `POST /api/approvals/{id}/reject`

Important later fix:

Rejecting a pending run approval now cancels the waiting run. This avoids a
bad state where the approval is rejected but the run still appears paused.

---

### `backend/routers/tools.py`

New routes:

- `GET /api/tools`
- `PATCH /api/tools/{tool_id}`

Purpose:

- Show tool registry.
- Allow Settings UI to update enabled flag and approval policy.

---

### `backend/routers/agents.py`

Purpose:

- Use native runtime by default.
- Only use OpenClaw sync/list behavior if active runtime is `openclaw`.

Why this matters:

Agents can now exist in Mission Control without OpenClaw.

---

### `backend/routers/events.py`

Purpose:

- Keep old SSE path alive.
- Make gateway-style status compatibility read from runtime status where
  possible.

---

### `backend/routers/orchestrator.py`

Purpose:

- Make orchestrator status understand native run status/current step.

Important behavior:

- Reads native run id from compatibility field.
- Returns run status and step state for UI.

---

### `backend/requirements.txt`

Added:

- `pydantic-ai`
- `langgraph`

Important note:

Adding packages is not the same as fully using them. The branch prepares the
dependency direction; deeper integration remains future work.

---

### `start.sh`

Purpose:

- Startup messaging now describes Mission Control native runtime.
- OpenClaw is optional.

Expected direction:

Do not block normal startup on local OpenClaw. Native mode should be the
default and should be quick to start.

---

## 3. Frontend Files Changed

### `frontend/src/hooks/useGatewayStatus.ts`

Historical name remains for compatibility, but behavior changed.

Current behavior:

- Polls `/api/runtime/status`.
- Provides sidebar status such as runtime ready/offline.

Future cleanup:

Rename to something like `useRuntimeStatus.ts`.

---

### `frontend/src/components/layout/Sidebar.tsx`

Changes:

- Adds Runs navigation item.
- Footer/status copy now reflects runtime readiness instead of gateway-only
  connection.

---

### `frontend/src/App.tsx`

Change:

- Adds `/runs` route.

---

### `frontend/src/pages/Runs.tsx`

New page.

Purpose:

- Acts as the native runtime prototype lab.

Main features:

- Start a Project Builder run.
- Show recent runs.
- Select a run.
- Load event timeline.
- Display pending approval for selected run.
- Approve/reject.
- Show final report.

Important UX point:

This page is the easiest place to verify whether native runtime is actually
working.

---

### `frontend/src/pages/Settings.tsx`

Rebuilt around native runtime concepts.

Sections:

- Runtime
- Providers/OpenRouter
- Models
- Tools
- Approvals
- Recent Runs

Capabilities:

- Save OpenRouter key.
- Test OpenRouter key.
- Load model list.
- Configure model purposes.
- Toggle tools and approval policy.
- See pending approvals.
- See recent runs.

---

## 4. Verification Done

Python syntax compile passed for the new backend files.

Frontend build passed:

```text
npm run build
```

Result:

- Build succeeded.
- Vite chunk-size warning only.

Browser-visible workflow with OpenRouter:

- Settings page key test succeeded.
- Runs page started Project Builder.
- Real model output appeared.
- Approval appeared.
- Approve resumed the run.
- Run completed.

Important limitation:

The browser-visible workflow used a local prototype API harness because the
full FastAPI dependency setup was blocked in the verification environment.
The real backend still needs one clean end-to-end verification pass in a
properly installed environment.

---

## 5. What Was Not Done Yet

Not done:

- Full Pydantic AI agent implementation.
- Full LangGraph durable checkpoint workflow.
- Real repository tool execution.
- Real patch application.
- Real test command execution through approved tools.
- SSE replay from database-backed event stream.
- Secret storage hardening beyond basic redaction.
- Complete UI copy cleanup from OpenClaw to native runtime.
- Complete automated test suite.

Do not mistake the current prototype for the final runtime. It is the
foundation and first working vertical slice.

