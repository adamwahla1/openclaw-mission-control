# 10 - Native Runtime Prototype Browser Test

**Date:** 2026-05-17
**Purpose:** Record exactly what was browser-tested with active OpenRouter
model output.

---

## 1. Test Goal

The user wanted to see Mission Control tested through the browser with a real
AI model behind it, not only placeholders.

The target workflow:

1. Configure OpenRouter in Settings.
2. Test the key.
3. Start a Project Builder run.
4. See real model output in the timeline.
5. Hit a human approval pause.
6. Approve it.
7. See the run complete.

---

## 2. Test Environment

Browser:

- Codex in-app browser.

Frontend URL:

```text
http://localhost:3000
```

Backend behavior:

- A local prototype API harness was used to simulate the intended FastAPI
  endpoints.
- The harness made real OpenRouter API calls.
- The harness is not part of the repo and should not be committed.

Why a harness was used:

- The full FastAPI backend dependency setup was blocked in the local
  verification environment.
- The goal at that moment was to prove the browser workflow and real
  OpenRouter interaction while the user could watch.

Important limitation:

This test does not replace a real FastAPI end-to-end test.

---

## 3. Provider Test

The user provided an OpenRouter key.

Security handling:

- The key must not be copied into docs.
- The key should be rotated/revoked after testing because it was pasted into
  chat.

Observed result:

```text
Connected. 356 models available.
```

Meaning:

- Browser UI could submit key.
- API layer could reach OpenRouter.
- Model discovery worked.

---

## 4. Run Test

Page:

```text
/runs
```

Run title:

```text
OpenRouter Live Prototype Test
```

Observed timeline:

- Implementation Plan appeared.
- Context Research appeared.
- Draft Build Plan appeared.
- Approval Required appeared.
- User clicked Approve.
- Run resumed.
- Critical Review appeared.
- Validation Plan appeared.
- Final Report appeared.
- Status became completed.

This proves the prototype UI flow:

- start run
- show event timeline
- call real model
- pause for approval
- resume after approval
- show final report

---

## 5. What Was Real

Real:

- Browser interaction.
- OpenRouter key test.
- OpenRouter model discovery.
- OpenRouter model calls.
- UI rendering of timeline.
- UI approval click.
- UI final report state.

Not fully real:

- Full FastAPI backend.
- SQLite native runtime persistence from real backend.
- Production SSE reconnect behavior.
- Real repository tools.
- Real patch/test execution.

---

## 6. Issues Observed

### Stale Dashboard Copy

Dashboard still said:

```text
Connect to OpenClaw Gateway in Settings to enable live agent execution.
```

This is stale and should be changed.

Better direction:

```text
Configure a provider in Settings to enable native agent execution.
```

### Final Report Quality

The prototype final report could be stronger, especially around review detail.

The real runtime code should make final reports structured and complete:

- summary
- plan
- changes/artifacts
- review findings
- test results
- approvals
- cost
- next steps

---

## 7. Required Follow-Up Test

Repeat this exact workflow against the real backend:

1. Clean install backend dependencies.
2. Start FastAPI backend.
3. Start Vite frontend.
4. Open `/settings`.
5. Configure OpenRouter.
6. Test key.
7. Open `/runs`.
8. Start Project Builder run.
9. Confirm events persist in SQLite.
10. Approve pending approval.
11. Confirm run resumes and completes.
12. Refresh browser.
13. Confirm timeline reloads from persisted events.

Only after that should anyone claim the full native runtime prototype is
end-to-end verified.

