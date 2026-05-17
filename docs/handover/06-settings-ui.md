# 06 - Settings UI, Runtime, Providers, Models, Tools

The Settings page is no longer only a gateway URL/token page. It is now the
control room for the native runtime prototype.

File:

```text
frontend/src/pages/Settings.tsx
```

---

## 1. Page Purpose

The Settings page should answer these questions for the user:

1. Which runtime is active?
2. Is Mission Control ready to run agents locally?
3. Is OpenRouter configured?
4. Which models should be used for planning, building, reviewing, cheap work,
   and long-context work?
5. Which tools are enabled?
6. Which tools require approval?
7. Are any approvals waiting?
8. What recent runs happened?

The page should not make OpenClaw feel required.

---

## 2. Runtime Section

Backend routes:

- `GET /api/runtime/status`
- `PUT /api/runtime/active`

Expected runtime options:

- `native`
- `openclaw`

Default:

- `native`

UI behavior:

- Show native runtime as the recommended/default path.
- Show OpenClaw as optional integration.
- If switching to OpenClaw, warn that it requires gateway setup.

Backend behavior:

- `native` should not require gateway connection.
- `openclaw` should start/use OpenClaw adapter.

---

## 3. Providers Section

Backend routes:

- `GET /api/providers`
- `POST /api/providers`
- `POST /api/providers/openrouter/test`
- `GET /api/providers/openrouter/models`

First provider:

- OpenRouter

UI capabilities:

- Enter API key.
- Save API key.
- Test API key before trusting it.
- Show connected/disconnected state.
- Show model count when model discovery works.

Security rules:

- Never display the full API key after save.
- Never write a real key into docs.
- Never commit test keys.
- Use placeholder examples only.

Example placeholder:

```text
sk-or-v1-REPLACE_ME
```

Important testing note:

A user-provided OpenRouter key was used in browser testing. That key should
be rotated/revoked after testing because it was pasted into a chat.

---

## 4. Models Section

Backend routes:

- `GET /api/model-configs`
- `POST /api/model-configs`

Seeded model purposes:

- `planner`
- `builder`
- `reviewer`
- `cheap_fast`
- `long_context`

Why purposes matter:

Different parts of Project Builder need different strengths.

Example:

- Planner may need a strong reasoning model.
- Builder may need a strong coding model.
- Reviewer may need a careful critic model.
- Cheap/fast can handle small summaries.
- Long-context can inspect large transcripts or docs.

Current model config should support:

- provider
- model id
- routing policy
- enabled flag
- optional metadata

---

## 5. Tools Section

Backend routes:

- `GET /api/tools`
- `PATCH /api/tools/{tool_id}`

Seeded tools:

- `repo.read`
- `repo.search`
- `repo.draft_patch`
- `tests.run`
- `report.summarize`

Each tool has:

- name
- description
- risk level
- approval mode
- enabled flag
- schema metadata

Approval posture:

- Read-only tools can be automatic.
- Write tools should require approval by default.
- Destructive, external, or financial tools should always be treated with
  extra caution.

The Settings UI should make this easy to understand without using too much
technical language.

---

## 6. Approvals Section

Backend routes:

- `GET /api/approvals`
- `POST /api/approvals/{id}/approve`
- `POST /api/approvals/{id}/reject`

Approval statuses:

- `pending`
- `approved`
- `rejected`

Native Project Builder behavior:

- Draft write-risk action creates approval.
- Run pauses.
- UI shows approval.
- Approve resumes run.
- Reject cancels run.

Good UI behavior:

- Show what action is being requested.
- Show risk level.
- Show run/task context.
- Make approve/reject actions clear.

---

## 7. Recent Runs Section

Backend routes:

- `GET /api/runs`
- `GET /api/runs/{id}`
- `GET /api/runs/{id}/events`

Purpose:

- Let the user see if the runtime is doing real work.
- Provide a trail back to run timeline and final report.

The dedicated Runs page is still the better place to inspect full details.

---

## 8. Legacy Gateway Settings

Old Settings UI managed:

- gateway URL
- gateway token
- device identity
- reconnect
- pairing diagnostics

Those concepts are now legacy/optional OpenClaw adapter settings.

Do not remove them blindly if OpenClaw adapter support is still desired.
But do not place them above the native runtime/provider controls.

Correct product hierarchy:

1. Runtime
2. Providers
3. Models
4. Tools
5. Approvals
6. Runs
7. Optional OpenClaw adapter details

