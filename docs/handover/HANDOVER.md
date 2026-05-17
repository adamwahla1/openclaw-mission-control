# Mission Control Native Runtime - Master Handover

**Date:** 2026-05-17
**Repo:** https://github.com/adamwahla1/openclaw-mission-control
**Working branch:** `native-runtime-readiness`
**Pull request:** https://github.com/adamwahla1/openclaw-mission-control/pull/1
**Local verification copy:** `C:\Users\aawah\Documents\Codex\mc-native-verify2\openclaw-mission-control-native-runtime-readiness`

This document is the first file a new engineer or AI agent should read.
It deliberately repeats important ideas in plain language because the next
reader may have less context, weaker reasoning, or no memory of the planning
conversation.

The most important product decision is this:

**Mission Control is no longer OpenClaw-first. Mission Control is becoming
a local-first, supervised, native AI agent runtime. OpenClaw should now be
treated as an optional adapter, not as the core runtime.**

If another model reads older files or old commit history and concludes that
Mission Control must connect to OpenClaw before it can do useful work, that
model is reading stale context. The current direction is native-first.

---

## 1. Current Product Definition

Mission Control is a full-stack web app for supervising AI agents, project
builder workflows, tool use, approvals, memory, cost, and execution traces.

The intended user experience is:

1. The user starts Mission Control locally.
2. Mission Control boots even when OpenClaw is not installed, not running, or
   not configured.
3. The user configures a model provider, first OpenRouter.
4. The user creates or selects an agent.
5. The user starts a session or a Project Builder run.
6. Mission Control streams the run timeline into the UI.
7. Risky actions pause for human approval.
8. The user approves or rejects the action.
9. Mission Control resumes, records all events, stores costs, and shows a
   final report.

OpenClaw can still exist, but only as one possible external runtime adapter.
It must not be required for the default app path.

---

## 2. Read These Files In Order

Read this file first, then read the rest in this exact order:

1. [`01-architecture.md`](./01-architecture.md) - Native-first architecture,
   process map, runtime registry, provider layer, run/event ledger.
2. [`02-session-changes.md`](./02-session-changes.md) - File-by-file record of
   what changed in the native runtime readiness implementation.
3. [`03-openclaw-bugs.md`](./03-openclaw-bugs.md) - Legacy OpenClaw gateway
   bug notes. Read only if working on the optional OpenClaw adapter.
4. [`04-local-gateway-setup.md`](./04-local-gateway-setup.md) - Legacy local
   OpenClaw setup. Not needed for native runtime mode.
5. [`05-remote-gateway-vps.md`](./05-remote-gateway-vps.md) - Legacy remote
   OpenClaw notes. Do not treat these as current product setup.
6. [`06-settings-ui.md`](./06-settings-ui.md) - Current Settings page:
   Runtime, Providers, Models, Tools, Approvals, Runs.
7. [`07-runbook.md`](./07-runbook.md) - How to run, configure, test, and debug
   the native runtime prototype.
8. [`08-open-issues.md`](./08-open-issues.md) - Current gaps, risks, and next
   implementation priorities.
9. [`09-this-session.md`](./09-this-session.md) - Latest session summary,
   implementation status, verification, and browser test notes.
10. [`10-native-runtime-prototype-test.md`](./10-native-runtime-prototype-test.md)
    - Detailed record of the OpenRouter/browser workflow test.
11. [`CHANGELOG.md`](../../CHANGELOG.md) - Historical feature timeline.

---

## 3. Stack

Frontend:

- React 19
- Vite
- TypeScript
- Tailwind CSS
- shadcn/ui style components
- Zustand where local app state is already used
- Server-Sent Events for live updates from backend to browser

Backend:

- FastAPI
- Python 3.11+
- SQLite in WAL mode
- Pydantic models for request/response validation
- Native runtime services under `backend/services`
- Routers under `backend/routers`

Native AI direction:

- OpenRouter is the first provider.
- Pydantic AI is intended for typed single-agent execution, structured
  outputs, and tool validation.
- LangGraph is intended for durable multi-step workflows, checkpoints,
  retries, and human interrupts.

Important nuance:

The first readiness implementation added the native runtime foundation and
optional imports for Pydantic AI and LangGraph. It does not yet use every
advanced Pydantic AI or LangGraph capability deeply. The current code should
be treated as a working prototype foundation, not the final agent engine.

---

## 4. What Was Built In The Native Runtime Readiness Work

The branch introduces these major concepts:

- `RuntimeRegistry`
  - Keeps track of the active runtime.
  - Defaults to `native`.
  - Can optionally activate `openclaw`.

- `NativeMissionControlRuntime`
  - Owns local agents, sessions, messages, runs, events, approvals, and
    artifacts.
  - Can create agents and sessions without OpenClaw.
  - Can start a Project Builder run.
  - Emits run events that the UI can display.
  - Creates an approval before simulated write-risk work.
  - Resumes a paused run after approval.

- Provider layer
  - Adds `ModelProvider` abstraction.
  - Adds `OpenRouterProvider`.
  - Supports provider config storage.
  - Supports model purpose config such as planner, builder, reviewer,
    cheap/fast, and long-context.
  - Records usage/cost metadata when available.

- Durable native schema
  - Adds runtime/provider/run/session/message/artifact/tool tables.
  - Extends approvals to be useful for native runtime work.
  - Seeds default runtime config, model purposes, and tool registry entries.

- Runs page
  - New `/runs` route.
  - Starts Project Builder prototype runs.
  - Shows run status.
  - Shows persisted event timeline.
  - Shows approval UI for paused runs.
  - Shows final report when complete.

- Settings page redesign
  - Runtime section.
  - OpenRouter provider section.
  - Model configuration section.
  - Tool approval policy section.
  - Approvals section.
  - Recent runs section.

---

## 5. Current API Surface

Native runtime APIs:

- `GET /api/runtime/status`
- `PUT /api/runtime/active`
- `GET /api/providers`
- `POST /api/providers`
- `POST /api/providers/openrouter/test`
- `GET /api/providers/openrouter/models`
- `GET /api/model-configs`
- `POST /api/model-configs`
- `GET /api/runs`
- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `POST /api/runs/{run_id}/cancel`
- `POST /api/runs/{run_id}/resume`
- `GET /api/approvals`
- `POST /api/approvals`
- `POST /api/approvals/{id}/approve`
- `POST /api/approvals/{id}/reject`
- `GET /api/tools`
- `PATCH /api/tools/{tool_id}`

Existing APIs that remain for compatibility:

- `/api/agents`
- `/api/orchestrator`
- `/api/debates`
- `/api/autopilot`
- `/api/memories`
- `/api/costs`
- `/api/gateway/*`

Important compatibility note:

Some database columns still have names like `gateway_agent_id` and
`gateway_session_id`. In native mode these must be interpreted as optional
external references or compatibility storage, not as proof that OpenClaw is
the primary runtime.

---

## 6. Expected Native Workflow

Project Builder v1 currently behaves like this:

1. User starts a run from `/runs`, or a task dispatch starts a run through the
   orchestrator.
2. Backend creates a row in `runs`.
3. Backend creates step and event rows in `run_steps` and `run_events`.
4. Runtime performs these high-level phases:
   - intake
   - plan
   - research
   - build draft
   - approval pause
   - review
   - test plan
   - final report
5. If an OpenRouter key is configured, the provider layer calls a real model.
6. If no provider key is configured, the runtime falls back to offline
   placeholder text so the app still demonstrates the workflow.
7. The run pauses before a write-risk tool.
8. The user approves or rejects from the UI.
9. Approval resumes the run.
10. Rejection cancels the waiting run.
11. Final report is stored as an artifact and shown in the UI.

---

## 7. Verification Already Done

Backend syntax verification passed for the new runtime files.

Frontend production build passed:

- `npm run build`
- Result: build succeeded.
- Warning: Vite reported a large chunk size. That is not a blocker for the
  prototype.

Browser-visible prototype test with active OpenRouter model:

- The Settings page accepted a user-provided OpenRouter key.
- Provider test returned success and a model count.
- Runs page started a Project Builder run.
- Real OpenRouter model output appeared in the run timeline.
- Approval appeared.
- Approval click resumed the run.
- Run completed and final report appeared.

Important honesty note:

The browser test used a local prototype API harness that matched the intended
backend endpoints because the full FastAPI dependency setup was blocked in the
local verification environment. This means:

- Frontend workflow and endpoint contract were browser-tested with real
  OpenRouter calls.
- Backend Python files were syntax-checked.
- The complete real FastAPI backend still needs one clean end-to-end run in a
  fully installed Python environment.

---

## 8. Current Security Note

The user pasted an OpenRouter key into the conversation during testing.
Do not copy that key into docs, logs, screenshots, commits, or examples.
The user should rotate or revoke that key after testing.

Docs and code examples must use placeholders such as:

```text
sk-or-v1-REPLACE_ME
```

---

## 9. Highest Priority Next Steps

1. Run the real FastAPI backend with dependencies installed and repeat the
   browser workflow against the real backend, not the prototype harness.
2. Finish replacing stale OpenClaw wording in older UI copy, especially the
   Dashboard message that still says to connect to OpenClaw.
3. Deepen the native runtime from prototype flow into true Pydantic AI and
   LangGraph execution.
4. Add true SSE replay from persisted `run_events` so browser reconnect never
   loses timeline state.
5. Add real supervised tools for repository read/search/draft/test/report.
6. Add stronger provider key handling and local secret hygiene.
7. Add automated tests for runtime, providers, approvals, and run event replay.

---

## 10. Mental Model For The Next Owner

Think of Mission Control as three layers:

1. Product layer:
   - Pages, runs, tasks, approvals, trace views, cost dashboards.

2. Runtime layer:
   - Native runtime by default.
   - Optional OpenClaw adapter later.
   - Future adapters can be added without changing the UI model.

3. Provider/tool layer:
   - OpenRouter first.
   - More providers later.
   - Tools are supervised and risk-tagged.

The UI should care about Mission Control concepts: agents, sessions, runs,
events, approvals, tools, cost, memory, artifacts.

The UI should not care whether the work was executed by native runtime,
OpenClaw, LangGraph, Pydantic AI, or another future engine.

