# 07 - Native Runtime Runbook

This runbook explains how to start, configure, and test Mission Control in
native runtime mode.

Native mode means:

- No OpenClaw gateway is required.
- Mission Control owns agents, sessions, runs, events, approvals, and tools.
- OpenRouter can provide real model output.

---

## 1. Start The App

From the repo root:

```bash
./start.sh
```

Expected dev URLs:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:3100`

Exact ports may differ if `APP_PORT` is set.

---

## 2. Health Checks

Backend health:

```bash
curl http://localhost:3100/health
```

Runtime status:

```bash
curl http://localhost:3100/api/runtime/status
```

Expected native-ready shape:

```json
{
  "active_runtime": "native",
  "runtime_ready": true
}
```

The exact response may include additional compatibility fields.

---

## 3. Configure OpenRouter

In the UI:

1. Open `/settings`.
2. Find Providers / OpenRouter.
3. Paste an OpenRouter API key.
4. Click save.
5. Click test.
6. Confirm the UI reports connected and shows a model count.

Do not commit the key. Do not paste it into docs.

If testing by API:

```bash
curl -X POST http://localhost:3100/api/providers \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openrouter",
    "enabled": true,
    "config": {
      "api_key": "sk-or-v1-REPLACE_ME"
    }
  }'
```

Test:

```bash
curl -X POST http://localhost:3100/api/providers/openrouter/test \
  -H "Content-Type: application/json" \
  -d '{"api_key":"sk-or-v1-REPLACE_ME"}'
```

---

## 4. Configure Model Purposes

Open `/settings`, then configure defaults for:

- planner
- builder
- reviewer
- cheap_fast
- long_context

If unsure, choose a working OpenRouter model for all purposes first. The goal
is to prove the workflow. Fine-tuning model choices can come later.

---

## 5. Start A Project Builder Run

In the UI:

1. Open `/runs`.
2. Enter a clear task title or prompt.
3. Start a Project Builder run.
4. Watch the timeline.
5. Wait for an approval card.
6. Click Approve.
7. Confirm the run resumes.
8. Confirm the run completes.
9. Read the final report.

Expected event categories:

- run started
- step started
- model output
- step completed
- approval required
- approval approved
- run completed

API alternative:

```bash
curl -X POST http://localhost:3100/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "project_builder",
    "title": "Prototype test",
    "input": "Build a tiny feature plan and report."
  }'
```

Then list events:

```bash
curl http://localhost:3100/api/runs/RUN_ID/events
```

---

## 6. Approval Flow

List approvals:

```bash
curl http://localhost:3100/api/approvals
```

Approve:

```bash
curl -X POST http://localhost:3100/api/approvals/APPROVAL_ID/approve \
  -H "Content-Type: application/json" \
  -d '{"decision_payload":{"note":"Approved for test"}}'
```

Reject:

```bash
curl -X POST http://localhost:3100/api/approvals/APPROVAL_ID/reject \
  -H "Content-Type: application/json" \
  -d '{"decision_payload":{"note":"Rejected for test"}}'
```

Expected behavior:

- Approve resumes waiting run.
- Reject cancels waiting run.

---

## 7. Cost/Usage Checks

Provider calls should record cost/usage metadata where available.

Check cost API:

```bash
curl http://localhost:3100/api/costs
```

The exact cost output depends on existing cost dashboard routes. The important
new storage fields are:

- provider
- requested_model
- actual_model
- latency_ms
- native_run_id

---

## 8. Logs

Backend logs:

- stdout of `start.sh` / uvicorn process

Frontend logs:

- browser console
- Vite terminal output

OpenClaw logs:

- Only relevant if optional OpenClaw runtime is active.

---

## 9. Common Problems

### App still talks about OpenClaw on Dashboard

Known stale copy. Update Dashboard text to native runtime language.

### OpenRouter test fails

Possible causes:

- Key is invalid.
- Key was revoked.
- Network blocked.
- OpenRouter API changed.
- Provider route is not mounted.

Check:

```bash
curl http://localhost:3100/api/providers
```

### Run only shows placeholder text

Possible causes:

- No provider configured.
- Model config missing.
- Provider call failed and runtime fell back offline.

Check Settings provider state first.

### Approval appears but run never resumes

Check:

```bash
curl http://localhost:3100/api/approvals
curl http://localhost:3100/api/runs/RUN_ID
curl http://localhost:3100/api/runs/RUN_ID/events
```

Expected run status before approval:

```text
waiting_approval
```

Expected run status after approval:

```text
running, then completed
```

### Full backend cannot start locally

The earlier browser verification had dependency/environment issues for full
FastAPI startup. If this happens:

1. Create a clean Python environment.
2. Install `backend/requirements.txt`.
3. Verify Pydantic AI and LangGraph can install on the machine.
4. Run backend syntax compile.
5. Start uvicorn.

---

## 10. Optional OpenClaw Mode

Only use this if specifically testing legacy adapter support.

Switch runtime:

```bash
curl -X PUT http://localhost:3100/api/runtime/active \
  -H "Content-Type: application/json" \
  -d '{"runtime":"openclaw"}'
```

Then follow the legacy OpenClaw docs:

- `03-openclaw-bugs.md`
- `04-local-gateway-setup.md`
- `05-remote-gateway-vps.md`

Do not use OpenClaw setup as the default path for new native runtime work.

