# 03 - Legacy OpenClaw Bugs And Workarounds

This file is legacy adapter context.

Mission Control no longer needs OpenClaw to boot or run the native prototype.
Read this file only if you are maintaining the optional OpenClaw runtime
adapter.

Do not treat these issues as blockers for native runtime work.

---

## 1. Why This File Still Exists

Older Mission Control sessions integrated with OpenClaw Gateway over WebSocket.
That work produced useful knowledge:

- which OpenClaw version could start locally
- which flags avoided startup problems
- why remote gateways needed token-only auth
- why device pairing was hard to operate

The knowledge is preserved because OpenClaw may remain an optional integration.
But it is no longer the primary architecture.

---

## 2. OpenClaw v2026.4.24 CPU Spin

Symptom:

- `openclaw gateway run` used high CPU.
- Gateway never became ready.
- Port `18789` did not respond.
- Logs were not useful.

Suspected root cause:

- Pricing bootstrap blocked the Node.js event loop in the sandbox.

Workaround:

- Use OpenClaw v2026.4.25.
- Set:

```json
{
  "gateway": {
    "pricing": {
      "bootstrap": false
    }
  }
}
```

Native runtime relevance:

- None unless testing optional OpenClaw adapter.

---

## 3. Silent Death Without Verbose Logs

Symptom:

- Gateway process exited quickly.
- No useful stdout/stderr.

Workaround:

```bash
openclaw gateway run --bind loopback --port 18789 --allow-unconfigured --verbose
```

Native runtime relevance:

- None unless running OpenClaw adapter.

---

## 4. Bonjour/mDNS Plugin Crash

Symptom:

- Gateway crashed trying to bind mDNS/Bonjour.

Workaround:

```bash
OPENCLAW_DISABLE_BONJOUR=1
```

And in OpenClaw config:

```json
{
  "plugins": {
    "deny": ["bonjour", "phone-control", "talk-voice"]
  }
}
```

Native runtime relevance:

- None.

---

## 5. Missing `chokidar` For Memory Plugin

Symptom:

```text
plugin memory-core failed to load: Cannot find module 'chokidar'
```

Effect:

- Non-fatal for gateway startup.
- OpenClaw memory plugin may not watch files.

Native runtime relevance:

- Low. Mission Control native memory should live in Mission Control data
  stores, not OpenClaw plugin state.

---

## 6. Token Handling Differences

Earlier integration learned:

- Some OpenClaw gateway versions expect token in WebSocket query string.
- Remote/shared gateways may use token-only auth instead of Ed25519 pairing.
- Local gateways used Ed25519 device identity.

Native runtime relevance:

- Only matters if keeping `gateway_bridge.py` working as an optional adapter.

---

## 7. Keep Or Remove?

Keep this file while:

- `OpenClawRuntimeAdapter` exists.
- `gateway_bridge.py` exists.
- Users may want to connect Mission Control to OpenClaw.

Remove this file only after:

- Product decision is made to delete OpenClaw support entirely.
- Code and UI references have also been removed.

