# 08 — Open issues & next steps

## 8.1 Open issues

### A. VPS device pairing not yet approved
- **State:** MC connects to `wss://openclaw-npt3.srv1624328.hstgr.cloud`,
  Ed25519 auth succeeds, gateway returns `DEVICE_PAIRING_REQUIRED`.
- **Owner:** ops (the user) — needs admin action on the VPS.
- **Action items:**
  1. `GET /api/gateway/device` from MC → grab `device_id` and public
     key.
  2. SSH into VPS or use VPS-side admin UI; approve that device id.
  3. Click Reconnect in MC's Settings page.
- **Code work needed in MC:** none.

### B. No model providers configured on the local gateway
- **State:** `models.providers = {}` in
  `/tmp/oc-home/.openclaw/openclaw.json`.
- **Effect:** `agent.run` will return "no provider available". MC's
  Agents/Sessions pages show empty model dropdowns.
- **Action items:** add OpenRouter / Kimi / Anthropic / etc. keys to
  `models.providers` and restart the gateway. See
  [04-local-gateway-setup.md §4.5](./04-local-gateway-setup.md).
- **Code work needed in MC:** later, a Settings sub-page to manage
  provider keys via gateway RPC would be nice.

### C. `chokidar` missing for `memory-core` plugin
- **State:** Non-fatal warning at gateway startup.
- **Effect:** OC's memory-core plugin doesn't load. MC stores its own
  memory in SQLite, so unaffected.
- **Action items:** ignore, or `npm i chokidar` in
  `.oc-v25/node_modules`.

### D. Auth status surfacing in UI is read-only
- **State:** Settings page shows "pairing required" / "connected" /
  "disconnected" with diagnostics, but offers no "Approve on
  gateway" button.
- **Reason:** That requires a paired admin device's `operator.admin`
  scope, which is exactly the device that's currently *not* paired.
  Chicken-and-egg.
- **Action items:** if a separate admin MC instance exists, it can
  call `POST /api/gateway/pairing/approve/{id}` to approve siblings.
  Otherwise pair via gateway CLI on the host.

### E. `/api/gateway/reconnect` is currently a no-op confirmation
- **State:** Endpoint returns "ok" but doesn't proactively close the
  WS — relies on the connection loop's natural reconnect behaviour.
- **Effect:** "Reconnect" button in UI may take up to one keepalive
  cycle to take effect.
- **Action items:** mirror the WS-close logic from
  `update_gateway_settings()` minus the save step.

### F. Token in WS query string shows up in some logs
- **State:** We redact in our own logger, but reverse proxy access
  logs may not.
- **Action items:** if deploying behind nginx/Cloudflare with logs,
  add a query-string redaction rule for `token=`.

## 8.2 Pending tasks (from prior session, still open)

These existed before this session and are unchanged:

- Phase 4 polish — Autopilot pipeline persistence (currently
  in-memory).
- Aegis security audit — needs more rule packs.
- Cost dashboard — needs richer breakdowns once provider keys are
  flowing real cost data.
- D3 memory neural map — performance work for >1k nodes.

## 8.3 Suggested next moves (in priority order)

1. **Approve the VPS device** so the user can drive a real gateway
   end-to-end and we can stress-test the bridge under remote
   latency / Cloudflare.
2. **Add at least one model provider** (OpenRouter) to the local
   gateway config so `agent.run` works for demos.
3. **Settings UI: connection-test button** — separate from "Save &
   Reconnect", so users can verify URL+token before persisting.
   Backend: open a transient WS with the candidate values, run the
   challenge handshake, return success/failure.
4. **Settings UI: providers sub-page** — list configured providers
   from gateway RPC, allow adding keys (writes go to
   `~/.openclaw/openclaw.json` via gateway, not via MC FS access).
5. **Harden identity file perms** — chmod 0600 on
   `~/.mission-control/identity/*`.
6. **Document the `operator.admin` scope contract** with the
   gateway team — confirm the union of `read+write` is intentional.

## 8.4 Useful commands cheat sheet

```bash
# What gateway is MC currently using?
curl -s localhost:$BACKEND_PORT/api/gateway/settings

# Force MC to forget gateway settings:
rm ~/.mission-control/gateway.json && pkill -HUP -f uvicorn

# Force MC to forget identity (full re-pair):
rm -rf ~/.mission-control/identity

# Reset local gateway from scratch:
rm -rf /tmp/oc-home && ./start.sh

# Check token redaction in MC log:
grep -i token /var/log/mc-backend.log     # should only show ***
```
