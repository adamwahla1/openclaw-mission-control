# 09 — This Session: Remote Gateway Connection Fixes

**Date:** 2026-05-07
**Session focus:** Fix connection to remote OpenClaw gateway (atomicbot.ai hosted)
**Commits:** `b01f5da`

---

## What the user needed

The user has an OpenClaw Gateway hosted at `https://7e4b2041f4.atomicbot.ai`
with a shared token. They were trying to connect Mission Control to it, but:

1. MC connected successfully over WebSocket
2. Handshake failed with `DEVICE_PAIRING_REQUIRED` (1008 policy violation)
3. The gateway kept closing the connection every reconnect attempt
4. No pairing request was visible on the gateway side

---

## Root cause

The MC `gateway_bridge.py` was doing the full OpenClaw Protocol v3 handshake:
- Receiving `connect.challenge` nonce
- Building an Ed25519-signed connect message with device identity
- Sending device public key + signature

This works for **local** gateways where MC is the first/primary operator client.
But **remote/shared** gateways (like atomicbot.ai) use a simpler model:
- Token is pre-configured in gateway auth
- Client just sends `auth: {token: "..."}` in the connect payload
- No device pairing needed, no Ed25519 signature required

When MC sent the signed connect, the remote gateway saw an unapproved device
and rejected it with `DEVICE_PAIRING_REQUIRED`.

---

## Changes made

### 1. `backend/services/gateway_bridge.py` — two fixes

**Fix A: Auto-convert `https://` → `wss://`**

```python
def _get_gateway_url(self) -> str:
    url = settings.gateway_url or device_auth.get_gateway_url()
    if not url:
        return url
    # Convert http(s) to ws(s)
    if url.startswith("https://"):
        url = "wss://" + url[len("https://"):]
    elif url.startswith("http://"):
        url = "ws://" + url[len("http://"):]
    return url.rstrip("/")
```

The user naturally enters `https://...` as the gateway URL (it's a web service).
But `websockets.connect()` requires a WebSocket scheme. Without this conversion,
the connection fails with a scheme error.

**Fix B: Token-only auth for remote gateways**

```python
# In _handshake(), after receiving challenge:
base_url = self._get_gateway_url()
is_local = any(h in base_url.lower() for h in ("localhost", "127.0.0.1", "::1"))

if gw_token and not is_local:
    # Remote gateway — use token-only connect (no Ed25519 signature)
    connect_msg = {
        "type": "req",
        "id": str(uuid.uuid4()),
        "method": "connect",
        "params": {
            "minProtocol": 3, "maxProtocol": 3,
            "client": {"id": "cli", "version": "0.1.0", ...},
            "role": "operator",
            "scopes": ["operator.admin"],
            "auth": {"token": gw_token},
        },
    }
else:
    # Local gateway — use full device auth with Ed25519 signature
    connect_msg = device_auth.build_connect(...)
```

This preserves Ed25519 auth for local gateways (security) while enabling
token-only for remote/shared gateways (compatibility).

### 2. `start.sh` — skip local gateway when remote configured

```bash
# Check for persisted remote gateway config
_REMOTE_GW=""
_MC_CFG="$HOME/.mission-control/gateway.json"
if [ -f "$_MC_CFG" ]; then
    _REMOTE_GW=$(python3 -c "..." "$_MC_CFG" 2>/dev/null)
fi
if [ -n "$MC_GATEWAY_URL" ] || [ -n "$OPENCLAW_GATEWAY_URL" ] || [ -n "$_REMOTE_GW" ]; then
    echo "🔗 Using remote OpenClaw Gateway (local gateway skipped)"
else
    ...  # boot local gateway as before
fi
```

Previously `start.sh` always tried to boot the local OpenClaw CLI gateway,
which spins at ~40% CPU for 60 seconds before giving up. When the user has
already configured a remote gateway, this is wasted time.

Now it detects the remote config and skips straight to backend + frontend.

---

## Current connection state

- **Status:** ✅ Connected and authenticated to `wss://7e4b2041f4.atomicbot.ai`
- **Method:** Token-only auth (no device pairing)
- **Working RPCs:** `health`, `status` (basic read-only methods)
- **Broken RPCs:** `agents.list`, `channels.status`, and anything requiring `operator.read` scope

The token provided by the user (`e6b5bf43...`) connects successfully but the
gateway reports `"scopes": []` in the auth payload. The gateway returns
`hello-ok` but denies any method requiring `operator.read` with:

```
{"code": "INVALID_REQUEST", "message": "missing scope: operator.read"}
```

## What the next owner needs to do

The token needs `operator.read` (and ideally `operator.write`, `operator.admin`)
scopes added on the gateway side. This is **gateway configuration**, not MC code:

1. The user's OpenClaw instance is hosted on atomicbot.ai
2. The gateway web UI (`https://7e4b2041f4.atomicbot.ai`) returns 403 on all paths
3. The canvas URL (from `status` RPC) also returns 403
4. The atomicbot.ai hosting provider likely has a control panel for token management

**Action:** The user (or atomicbot.ai support) needs to add scopes to the token.
MC will auto-reconnect and gain full access once the scopes are updated.

Alternatively, if the user generates a **new token with scopes**, they can paste
it into MC Settings → Save & Reconnect. No restart needed.

---

## Files modified this session

| File | Change |
|------|--------|
| `backend/services/gateway_bridge.py` | https→wss conversion, token-only auth for remote |
| `start.sh` | Skip local gateway when remote config detected |
| `docs/handover/09-this-session.md` | This document (new) |
| `CHANGELOG.md` | Complete project history (new) |
| `docs/handover/HANDOVER.md` | Updated index |
| `docs/handover/08-open-issues.md` | Updated with current state |
| `README.md` | Updated with current known issues |

---

## Testing notes

To verify the connection manually:

```python
import asyncio, websockets, json, ssl, uuid

url = "wss://7e4b2041f4.atomicbot.ai?token=e6b5bf43ad562c4f2c0cb5857285d9f833eb77d59281566fe0dc68821b82157d"

async def test():
    async with websockets.connect(url, ssl=ssl.create_default_context()) as ws:
        msg = await ws.recv()  # connect.challenge
        nonce = json.loads(msg)["payload"]["nonce"]

        await ws.send(json.dumps({
            "type": "req", "id": str(uuid.uuid4()), "method": "connect",
            "params": {
                "minProtocol": 3, "maxProtocol": 3,
                "client": {"id": "cli", "version": "0.1.0", "platform": "linux", "deviceFamily": "desktop", "mode": "cli"},
                "role": "operator", "scopes": [],
                "auth": {"token": "e6b5bf43ad562c4f2c0cb5857285d9f833eb77d59281566fe0dc68821b82157d"}
            }
        }))
        resp = await ws.recv()
        print(json.dumps(json.loads(resp), indent=2))

asyncio.run(test())
```

Expected: `"ok": true` with `type: "hello-ok"`, but `"auth": {"role": "operator", "scopes": []}`.

To test agents.list:
```python
await ws.send(json.dumps({"type": "req", "id": str(uuid.uuid4()), "method": "agents.list", "params": {}}))
resp = await ws.recv()
# Expected: ok=false, error={"code": "INVALID_REQUEST", "message": "missing scope: operator.read"}
```

---

## Handoff checklist

- [x] Remote gateway connection works (token-only auth)
- [x] https→wss auto-conversion works
- [x] start.sh skips local gateway for remote configs
- [x] Device auth (Ed25519) still works for local gateways
- [ ] Token scopes need to be added on gateway side (owner: user / atomicbot.ai)
- [ ] Once scopes are added, verify `agents.list`, `channels.status`, etc.
- [ ] Update Settings UI to show "scopes granted: X" from gateway auth payload
