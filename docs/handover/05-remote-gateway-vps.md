# 05 - Legacy Remote OpenClaw Gateway Notes

This file is legacy adapter context.

The current Mission Control direction is native runtime plus OpenRouter,
without requiring any remote OpenClaw gateway.

Do not use this file as the main setup guide.

---

## 1. Why This File Is Legacy

Earlier versions of Mission Control attempted to connect to remote OpenClaw
gateways over WebSocket. That created operational friction:

- gateway tokens needed specific scopes
- Ed25519 device pairing was hard to approve remotely
- hosted gateways differed in auth behavior
- Mission Control could appear broken even when the problem was gateway-side

The new native runtime avoids this by keeping execution inside Mission Control
and using provider APIs directly through a provider abstraction.

---

## 2. Security Note About Old Tokens

Older handover files contained concrete gateway URLs and tokens.

Those details have been removed from this updated handover because secrets
should not live in docs. If a token was ever pasted into chat or committed to
docs, rotate it.

Use placeholders only:

```text
wss://your-openclaw-gateway.example.com
REPLACE_WITH_GATEWAY_TOKEN
```

---

## 3. If You Still Need Remote OpenClaw

Only use this path if testing optional OpenClaw adapter support.

Expected inputs:

- Gateway URL, usually `wss://...`
- Gateway token with required operator scopes
- Optional device pairing approval depending on gateway auth mode

Possible auth modes:

- token-only remote auth
- Ed25519 device challenge and pairing

Common required scopes:

- `operator.read`
- `operator.write`
- `operator.admin`

If token lacks scopes, the gateway may accept the connection but reject useful
methods such as agent listing.

---

## 4. Native Runtime Replacement

For the current product path, do this instead:

1. Open Mission Control.
2. Keep runtime set to `native`.
3. Configure OpenRouter in Settings.
4. Configure model purposes.
5. Start a Project Builder run.
6. Approve risky tool request.
7. Inspect final report.

This gives the user a working AI-backed workflow without remote gateway
pairing or OpenClaw operator scopes.

