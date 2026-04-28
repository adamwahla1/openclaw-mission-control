# 06 — Settings UI & Token resolution chain

## 6.1 The page

`frontend/src/pages/Settings.tsx` (~330 lines).

Layout (top to bottom):

1. **Header:** title + connection-status pill (green = connected &
   authenticated, amber = connected but pairing required, red =
   disconnected).
2. **Connection card:**
   - Gateway URL input (e.g. `wss://gateway.example.com` or
     `ws://127.0.0.1:18789`)
   - Gateway Token input with show/hide eye toggle
   - Token preview line (e.g. `rwOVXP2p…`) and source badge
     (`env` / `persisted` / `auto`)
   - "Save & Reconnect" + "Reconnect" buttons
3. **Diagnostics card:** device id, has identity, has operator
   token, scopes, gateway auth mode, last auth error, server info.
4. **Quick Setup Guide:** numbered list with the four steps below.

## 6.2 API endpoints used

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/gateway/settings` | Read URL + token preview + source |
| PUT | `/api/gateway/settings` | Save URL+token, trigger reconnect |
| GET | `/api/gateway/status` | Live connection diagnostics (poll 5 s) |
| GET | `/api/gateway/device` | Device identity status |
| POST | `/api/gateway/reconnect` | Force reconnect (no settings change) |
| GET | `/api/gateway/pairing/pending` | (admin) list pending pairings |
| POST | `/api/gateway/pairing/approve/{id}` | (admin) approve a pairing |
| POST | `/api/gateway/pairing/reject/{id}` | (admin) reject a pairing |
| GET | `/api/gateway/agents` | Live agents from connected gateway |
| GET | `/api/gateway/status-rpc` | Live status RPC roundtrip |

## 6.3 Token resolution chain (definitive)

When MC needs to know which gateway URL/token to use, the chain is:

```
1.  $MC_GATEWAY_URL / $MC_GATEWAY_TOKEN
        ↓ (if blank)
2.  $OPENCLAW_GATEWAY_URL / $OPENCLAW_GATEWAY_TOKEN
        ↓ (if blank)
3.  ~/.mission-control/gateway.json
        ↓ (if blank or missing)
4.  Local OpenClaw config: ~/.openclaw/openclaw.json
       → gateway.auth.token
       → URL defaults to ws://127.0.0.1:18789
        ↓ (if local config missing)
5.  Default: ws://127.0.0.1:18789, no token
```

Step 1–2 are read at process start via pydantic `BaseSettings`.
Step 3 is loaded *after* by `load_gateway_settings()` and only
applied to fields that are still empty. Step 4 is the legacy
auto-detect path that supports co-installation with OpenClaw on the
same machine.

The "source" string returned by `GET /api/gateway/settings` is:
- `"env"` — env var supplied a value
- `"persisted"` — persisted file supplied a value
- `"auto"` — neither; auto-detected or default

## 6.4 What `Save & Reconnect` does, step by step

1. Frontend sends `PUT /api/gateway/settings` with `{url, token}`.
2. Router calls `gateway.update_gateway_settings(url, token)`.
3. `update_gateway_settings`:
   - Calls `save_gateway_settings(url, token)` →
     writes `~/.mission-control/gateway.json` and updates
     `settings.gateway_url/token` in memory.
   - Closes the existing WS (`self._ws.close()`).
   - Sets `_connected = False`, `_auth_status = "none"`.
4. The `_connection_loop` task wakes from its `await self._ws.recv()`,
   sees the connection is closed, loops, calls `_get_gateway_url()` /
   `_build_ws_url()` (which now read the new settings), and opens a
   new WS.
5. Frontend re-fetches `/api/gateway/settings` and
   `/api/gateway/status`, the status pill updates.

## 6.5 What `Reconnect` does (without changing settings)

Just hits `POST /api/gateway/reconnect`. The endpoint replies "ok"
immediately; the actual reconnect is handled by the connection
loop's normal "if disconnected, retry" path. Useful after the user
approves the device on the VPS side.

(Note: the current `/reconnect` endpoint doesn't proactively close
the WS — it just reports status. If a stronger reconnect is needed
in future, mirror what `update_gateway_settings` does without the
save step.)

## 6.6 Security notes

- Token is **never** returned by GET. Only first 8 chars + `...`.
- Token in PUT body is sent in plain JSON — fine over HTTPS,
  important to remember when running MC over plain HTTP locally
  (don't share localhost across users).
- WS URL has the token in the query string. This means:
  - Anything that logs the URL must redact (we replace with `***`
    in `_connection_loop` logger).
  - Reverse proxies in front of MC should also redact query
    strings in their access logs.
- Device private key lives at
  `~/.mission-control/identity/device.json` with default file mode.
  Consider tightening to `0600` in a future hardening pass.
