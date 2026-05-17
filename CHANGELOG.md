# Mission Control Changelog

This changelog preserves the project history while making the current
native-runtime direction clear.

---

## 2026-05-17 - Native Runtime Readiness

Mission Control changed direction from OpenClaw-first dashboard to
native-runtime-first command center.

Implemented:

- Native runtime schema:
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
  - extended `approvals`

- Runtime registry:
  - default runtime is `native`
  - optional runtime is `openclaw`
  - OpenClaw no longer starts as the core app dependency

- Native runtime service:
  - native agents
  - native sessions
  - native messages
  - Project Builder prototype runs
  - event persistence
  - approval pause/resume/cancel
  - report artifact storage

- Provider layer:
  - `ModelProvider` abstraction
  - `OpenRouterProvider`
  - provider config storage
  - OpenRouter key testing
  - model discovery
  - model purpose defaults
  - cost/usage metadata fields

- API routes:
  - `/api/runtime/status`
  - `/api/runtime/active`
  - `/api/providers`
  - `/api/providers/openrouter/test`
  - `/api/providers/openrouter/models`
  - `/api/model-configs`
  - `/api/runs`
  - `/api/runs/{id}/events`
  - `/api/runs/{id}/cancel`
  - `/api/runs/{id}/resume`
  - `/api/approvals`
  - `/api/approvals/{id}/approve`
  - `/api/approvals/{id}/reject`
  - `/api/tools`

- Frontend:
  - Settings redesigned around Runtime, Providers, Models, Tools, Approvals,
    and Recent Runs
  - Runs page added
  - Sidebar status uses runtime readiness
  - App route added for `/runs`

- Existing systems shifted native-first:
  - agents
  - orchestrator
  - AI client
  - health/runtime status

Verification:

- Backend syntax compile passed.
- Frontend build passed.
- Browser workflow was tested with real OpenRouter model output using a
  prototype API harness.

Known limitation:

- Full FastAPI end-to-end browser verification still needs to be run in a
  clean installed environment.

---

## Earlier History - OpenClaw-First Era

The project originally grew as OpenClaw Mission Control, a dashboard for an
OpenClaw Gateway. That history still explains many existing pages and some
legacy names.

### Phase 1 - Foundation + Tasks

Implemented:

- FastAPI backend
- SQLite database
- React/Vite frontend
- task board
- orchestrator
- agent factory
- live task/session views
- task reports

### Phase 2 - Projects + Debate

Implemented:

- projects
- project detail views
- multi-agent debate room
- Gemini-driven debate agents
- debate scoring and summaries

### Phase 3 - Memory + Office

Implemented:

- memory neural map with D3
- virtual office with canvas
- memory APIs
- office state APIs

### Phase 4 - Autopilot + Skills + Security + Cost

Implemented:

- autopilot pipelines
- skills hub
- registry integration
- security audit/Aegis
- cost dashboard

### Gateway Integration Era

Implemented:

- OpenClaw gateway bridge
- Ed25519 device identity
- token handling
- remote/local gateway settings
- Settings page for gateway diagnostics
- local OpenClaw gateway bootstrap
- remote token-only auth fixes

Current status of this era:

- Kept as optional adapter support.
- No longer the main product architecture.

---

## Documentation

The current handover docs live in:

```text
docs/handover/
```

Read first:

```text
docs/handover/HANDOVER.md
```

The handover docs were rewritten on 2026-05-17 so a future engineer or AI
agent sees native runtime as the current source of truth.

