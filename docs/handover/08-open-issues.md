# 08 - Open Issues And Next Steps

**Updated:** 2026-05-17

This file lists the important remaining work after the native runtime readiness
prototype.

---

## 1. Highest Priority Issues

### A. Real FastAPI end-to-end verification still needed

State:

- Python syntax compile passed.
- Frontend build passed.
- Browser-visible flow was tested with a local prototype API harness and real
  OpenRouter calls.

Gap:

- The exact same browser workflow still needs to be repeated against the real
  FastAPI backend in a fully installed environment.

Why it matters:

The prototype harness proved the UI and endpoint contract. It did not prove
that all real backend dependencies and routers run together cleanly.

Next action:

1. Install backend dependencies in a clean environment.
2. Start real backend.
3. Start frontend.
4. Configure OpenRouter.
5. Start run.
6. Approve run.
7. Confirm completion and final report.

---

### B. Dashboard still has stale OpenClaw-first copy

State:

- Browser test showed Dashboard copy that says to connect to OpenClaw Gateway.

Why it matters:

This contradicts the new product direction and may confuse users.

Next action:

- Update Dashboard and any other stale copy to say native runtime/provider
  setup, not OpenClaw setup.

---

### C. Native runtime is still prototype-level

State:

- Project Builder flow exists.
- It emits events.
- It pauses for approval.
- It can call OpenRouter.

Gaps:

- Pydantic AI is not yet the real single-agent execution engine.
- LangGraph is not yet the real durable workflow engine.
- Tools are not yet executing real repository actions.
- Patch drafting is not yet a real patch artifact flow.
- Test execution is not yet a supervised tool.

Next action:

- Implement Project Builder v1 as a real LangGraph workflow.
- Use Pydantic AI for typed planner/builder/reviewer outputs.
- Keep events visible and debuggable.

---

### D. SSE replay needs to be hardened

State:

- Events are persisted.
- UI can fetch events by run id.
- SSE broadcasting exists.

Gap:

- The ideal design is "SSE live plus persisted replay after reconnect."

Next action:

- Add event sequence numbers/cursors if not already sufficient.
- Let `/api/runs/{id}/events` support replay after a known event id.
- Ensure UI refresh never loses timeline state.

---

### E. Provider key storage needs hardening

State:

- Provider config exists.
- UI/API should redact secrets.

Gaps:

- Secret-at-rest story needs review.
- Local file/database permissions need review.
- Logs/screenshots must not leak keys.

Next action:

- Audit provider config responses.
- Ensure no full API key is returned after save.
- Consider OS keychain or encrypted local secret storage later.

---

### F. Cost accounting needs real validation

State:

- Provider cost recording fields exist.

Gaps:

- Need confirm actual OpenRouter usage response shape for all chosen models.
- Need verify cost dashboard reads native run costs correctly.

Next action:

- Add tests around `record_provider_cost`.
- Add UI trace view showing provider, requested model, actual model, tokens,
  latency, and cost.

---

## 2. Product-Level Next Steps

### 1. Native Project Builder v1

Build the flagship workflow fully:

1. Intake
2. Clarify if needed
3. Plan
4. Research
5. Draft build
6. Approval
7. Apply or stage patch
8. Run tests
9. Review
10. Revise
11. Final report

All phases should emit events.

### 2. Trace Page

Every run should have a trace page showing:

- prompt
- model
- provider
- tool calls
- approvals
- outputs
- errors
- tokens
- cost
- artifacts

### 3. Tool Registry Expansion

Add real tools:

- repository file read
- repository search
- draft patch
- apply patch after approval
- run tests after approval
- summarize test output
- generate report artifact

### 4. Memory Hooks

Native runtime should retrieve memory context before agent calls.

Short-term:

- keyword retrieval from existing memories

Later:

- embeddings
- semantic search
- memory quality scoring

### 5. Evals

Add fixtures for:

- Project Builder simple feature
- Project Builder bugfix
- research task
- debate task
- prompt injection attempt
- malformed provider output
- runaway budget prevention

---

## 3. OpenClaw-Related Issues

OpenClaw issues are now lower priority because native runtime is default.

Keep these only if maintaining optional adapter support:

- local OpenClaw CPU spin workarounds
- bonjour/mDNS failures
- remote gateway token scopes
- device pairing flows
- `gateway_bridge.py` reconnection behavior

Do not let these block native runtime progress.

---

## 4. Security And Safety Work

Important risks to address:

- Prompt injection through repository files or tool outputs.
- Excessive agency, such as writing files without approval.
- Sensitive data disclosure to model providers.
- Unbounded spending or runaway token usage.
- Malformed structured output from models.
- Tool output being trusted without validation.

Recommended guardrails:

- Human approval for write/destructive/external/financial tools.
- Explicit token/cost budgets per run.
- Tool schemas validated before execution.
- Model outputs parsed into typed structures where possible.
- Trace all prompts and tool calls.
- Redact secrets in UI and logs.

---

## 5. Cleanups

Naming cleanup:

- Rename `useGatewayStatus.ts` to `useRuntimeStatus.ts`.
- Rename old gateway compatibility columns when safe:
  - `gateway_agent_id`
  - `gateway_session_id`

Docs cleanup:

- Keep legacy OpenClaw docs but mark them optional.
- Make native runtime docs the default path everywhere.

UI cleanup:

- Remove or demote OpenClaw-first language.
- Make Runs page feel like a normal product page, not just a lab.
- Add better empty states for missing provider key/model config.

