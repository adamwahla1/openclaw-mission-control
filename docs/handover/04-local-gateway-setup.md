# 04 — Local OpenClaw Gateway setup

How the local gateway is wired. `start.sh` does this automatically;
this doc is for understanding / manual recovery.

## 4.1 Install

OpenClaw v2026.4.25 (the version with the `pricing.bootstrap` fix):

```bash
INSTALL_DIR=/data/users/LJTvWmv8w3YZfYb6dMwkwprDPJv1/Workspace/.oc-v25
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
npm i openclaw@2026.4.25
```

After install:
```
.oc-v25/
└── node_modules/
    └── .bin/
        └── openclaw          ← the CLI
```

## 4.2 Home directory & config

```bash
export OPENCLAW_HOME=/tmp/oc-home
mkdir -p $OPENCLAW_HOME/.openclaw
```

Note the **double-nested** `.openclaw` — the gateway's
`OPENCLAW_HOME` is the *parent* dir; the gateway then reads/writes
`OPENCLAW_HOME/.openclaw/openclaw.json`.

Bootstrap `openclaw.json`:

```json
{
  "gateway": {
    "mode": "local",
    "bind": "loopback",
    "auth": { "mode": "token", "token": "<40-char hex>" },
    "pricing": { "bootstrap": false }
  },
  "meta": { "lastTouchedVersion": "2026.4.25" },
  "models": { "mode": "merge", "providers": {} },
  "agents": {
    "defaults": {},
    "list": [{
      "id": "dev", "default": true,
      "identity": { "name": "Dev Agent", "theme": "assistant", "emoji": "🤖" }
    }]
  },
  "plugins": {
    "deny": ["bonjour", "phone-control", "talk-voice"],
    "entries": {}
  }
}
```

Generate a random token:
```bash
python3 -c "import secrets; print(secrets.token_hex(20))"
```

## 4.3 Run

```bash
OPENCLAW_HOME=/tmp/oc-home OPENCLAW_DISABLE_BONJOUR=1 \
  /data/.../.oc-v25/node_modules/.bin/openclaw \
  gateway run --bind loopback --port 18789 \
              --allow-unconfigured --verbose \
  > /tmp/openclaw-gateway.log 2>&1 &
```

Expected boot sequence (in `/tmp/openclaw-gateway.log`):
```
[gateway] loading config from /tmp/oc-home/.openclaw/openclaw.json
[plugins] loaded N plugins (1 failed: memory-core / chokidar) ← OK
[gateway] WS bound on ws://127.0.0.1:18789
[gateway] ready
```

Boot takes ~40 s. Wait until the port is listening:

```bash
for i in $(seq 1 60); do
  python3 -c "import socket;s=socket.socket();s.settimeout(1);s.connect(('127.0.0.1',18789));s.close()" \
    2>/dev/null && echo ready && break
  sleep 1
done
```

## 4.4 Verify

```bash
# Token is in the config file
TOKEN=$(python3 -c 'import json;print(json.load(open("/tmp/oc-home/.openclaw/openclaw.json"))["gateway"]["auth"]["token"])')

# Backend should already be connected. Check from MC side:
curl -s http://localhost:$BACKEND_PORT/api/gateway/status | jq
# Expect: connected:true, auth_status:"authenticated"
```

## 4.5 Adding model providers

The gateway's `models.providers` block is empty by default. To use
real models, add keys there. Example for OpenRouter:

```json
"models": {
  "mode": "merge",
  "providers": {
    "openrouter": { "apiKey": "sk-or-..." }
  }
}
```

Restart the gateway after editing. (MC has no UI for this yet —
this is a gateway-side concern. Could be added later as a Settings
sub-page.)

## 4.6 Stopping the gateway

```bash
pkill -f "openclaw gateway run"
# or kill by PID from start.sh
```

The devguard block in `start.sh` reaps stale listeners on the MC
ports but **not** on 18789. Stop the gateway manually if you need
to recycle it.

## 4.7 Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Port 18789 never opens | Pricing bootstrap or bonjour | Check log, verify `pricing.bootstrap:false` and bonjour deny |
| 401 from gateway | Token mismatch | Re-read token from `openclaw.json`, update `~/.mission-control/gateway.json` or env |
| Process exits silently | No `--verbose` | Add `--verbose`, read log |
| `chokidar` missing | memory-core plugin | Ignore (non-fatal) |
| MC can't connect at all | Wrong URL scheme | Use `ws://` for local, `wss://` for VPS |
