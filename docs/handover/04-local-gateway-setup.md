# 04 - Legacy Local OpenClaw Gateway Setup

This file is only for optional OpenClaw adapter testing.

Native Mission Control does not require this setup.

If your goal is to test the native runtime, OpenRouter, Project Builder runs,
approvals, or the Runs page, skip this file and use `07-runbook.md`.

---

## 1. When To Use This File

Use this only when:

- active runtime is intentionally set to `openclaw`
- you are debugging `OpenClawRuntimeAdapter`
- you are debugging `gateway_bridge.py`
- you are checking backward compatibility with old gateway-based flows

Do not use this for normal development.

---

## 2. Local Gateway Version

The last known workable local gateway version was:

```text
openclaw@2026.4.25
```

It was selected because it supports:

```json
{
  "gateway": {
    "pricing": {
      "bootstrap": false
    }
  }
}
```

That setting avoids an older CPU-spin startup problem.

---

## 3. Minimal Local Gateway Config

Use an isolated home:

```bash
export OPENCLAW_HOME=/tmp/oc-home
mkdir -p "$OPENCLAW_HOME/.openclaw"
```

Config path:

```text
/tmp/oc-home/.openclaw/openclaw.json
```

Example config:

```json
{
  "gateway": {
    "mode": "local",
    "bind": "loopback",
    "auth": {
      "mode": "token",
      "token": "REPLACE_WITH_RANDOM_TOKEN"
    },
    "pricing": {
      "bootstrap": false
    }
  },
  "models": {
    "mode": "merge",
    "providers": {}
  },
  "plugins": {
    "deny": ["bonjour", "phone-control", "talk-voice"],
    "entries": {}
  }
}
```

Generate a token:

```bash
python -c "import secrets; print(secrets.token_hex(20))"
```

---

## 4. Run Command

```bash
OPENCLAW_HOME=/tmp/oc-home OPENCLAW_DISABLE_BONJOUR=1 \
  openclaw gateway run \
  --bind loopback \
  --port 18789 \
  --allow-unconfigured \
  --verbose
```

Expected local URL:

```text
ws://127.0.0.1:18789
```

---

## 5. Native Runtime Alternative

For native runtime, the equivalent setup is much simpler:

1. Start Mission Control.
2. Open Settings.
3. Configure OpenRouter.
4. Start a run from `/runs`.

No local OpenClaw gateway, token, pairing, or port `18789` is required.

