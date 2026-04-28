# 02 — Session changes (file-by-file)

This document covers **every** code change made in this session, with
the rationale for each.

Diff summary:

```
 backend/config.py                  | 111 +++++/-19
 backend/routers/gateway.py         |  43 +++/-1
 backend/services/device_auth.py    | 135 +++/-30
 backend/services/gateway_bridge.py |  40 +++/-1
 frontend/src/pages/Settings.tsx    | 331 +++/-2
 start.sh                           |  66 ++++/-2
 tasks.json                         |  12 +/-2
 7 files changed, 644 insertions(+), 94 deletions(-)
```

---

## 2.1 `backend/config.py`

**Goal:** Make MC's gateway URL/token configurable via env vars,
persisted across restarts, and resolvable in a clear priority chain.

**Resolution priority** (high → low):
1. `MC_GATEWAY_URL` / `MC_GATEWAY_TOKEN` (pydantic env, prefix `MC_`)
2. `OPENCLAW_GATEWAY_URL` / `OPENCLAW_GATEWAY_TOKEN` (convention from
   reference MC repos like `crshdn/mission-control`)
3. Persisted file at `~/.mission-control/gateway.json`
4. Auto-detected from local OpenClaw config
   (`~/.openclaw/openclaw.json`), specifically
   `gateway.auth.token`. URL defaults to `ws://127.0.0.1:18789` in
   that case.
5. Default `ws://127.0.0.1:18789` with empty token.

Two new helper functions:

```python
def save_gateway_settings(url: str, token: str) -> None:
    """Persist gateway settings; updates runtime settings too."""
    config_dir = Path.home() / ".mission-control"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "gateway.json"
    data = {}
    if config_file.exists():
        try: data = json.loads(config_file.read_text())
        except Exception: pass
    data["gateway_url"] = url
    data["gateway_token"] = token
    config_file.write_text(json.dumps(data, indent=2))
    settings.gateway_url = url
    settings.gateway_token = token


def load_gateway_settings() -> dict:
    config_file = Path.home() / ".mission-control" / "gateway.json"
    if config_file.exists():
        try: return json.loads(config_file.read_text())
        except Exception: pass
    return {}
```

At module load, persisted settings override empty fields *only if*
no env var was set — so `MC_GATEWAY_URL=...` always wins over the
saved file.

**Why the prefix split (`MC_` vs `OPENCLAW_`)?** Pydantic
`BaseSettings` only accepts a single `env_prefix`. We use `MC_` for
the canonical names and read `OPENCLAW_*` manually so deployments
that already use that convention (matching `crshdn/mission-control`)
work without remapping.

---

## 2.2 `backend/services/device_auth.py`

**Goal:** Make the device identity self-contained so MC works
without any local OpenClaw install. Previously it expected the
keypair under `~/.openclaw/identity/device.json`.

Key changes:

```python
# New, MC-native location
MC_IDENTITY_DIR  = Path.home() / ".mission-control" / "identity"
MC_IDENTITY_PATH = MC_IDENTITY_DIR / "device.json"
MC_AUTH_PATH     = MC_IDENTITY_DIR / "device-auth.json"

# Active paths — prefer MC standalone, fall back to OC home
DEVICE_IDENTITY_PATH = MC_IDENTITY_PATH if MC_IDENTITY_PATH.exists() else OC_DEVICE_IDENTITY_PATH
DEVICE_AUTH_PATH     = MC_AUTH_PATH     if MC_IDENTITY_PATH.exists() else OC_DEVICE_AUTH_PATH
```

`save_device_identity()` defaults to writing the MC path. New
identities created from now on land under `~/.mission-control/`.

`load_device_identity()` looks at MC path first, then OC path, so
existing co-installed setups keep working.

`DeviceAuthManager.get_gateway_url()` and `get_gateway_token()` now
delegate to `config.settings`:

```python
def get_gateway_url(self) -> str:
    from config import settings
    return settings.gateway_url

def get_gateway_token(self) -> str:
    from config import settings
    return settings.gateway_token
```

This means **the single source of truth for which gateway to talk to
is `config.settings`**, not the local `openclaw.json` file. The
config layer is responsible for figuring out where that came from.

---

## 2.3 `backend/services/gateway_bridge.py`

**Goal:** Pass the gateway token in the WS URL query string (matches
reference MC implementations and is what the gateway actually
expects), bump scopes to `operator.admin`, and add a runtime
"reconfigure" path.

```python
def _get_gateway_url(self) -> str:
    if settings.gateway_url:
        return settings.gateway_url
    return device_auth.get_gateway_url()

def _build_ws_url(self) -> str:
    """Append ?token=... to the WS URL (matches reference MC pattern)."""
    base_url = self._get_gateway_url()
    token = settings.gateway_token or device_auth.get_gateway_token()
    if not token:
        return base_url
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}token={token}"
```

In `_connection_loop`, the URL is logged with the token redacted to
`***`.

Authentication scope upgraded:

```python
# old: ["operator.read", "operator.write"]
scopes=["operator.admin"],
```

This is needed for Mission Control to perform admin RPCs (creating
agents, running pipelines, etc.) — the gateway's `operator` namespace
splits read/write/admin and we want the union.

New runtime reconfig method:

```python
async def update_gateway_settings(self, url: str, token: str) -> None:
    from config import save_gateway_settings
    save_gateway_settings(url, token)
    if self._ws:
        await self._ws.close()
    self._connected = False
    self._auth_status = "none"
    # Connection loop wakes up and reconnects with the new settings
```

**Bug fixed during this work:** an earlier `str_replace` accidentally
joined two lines (`)                if _auth_d:`) producing a Python
SyntaxError. Re-applied with proper newline; verified by running the
backend.

---

## 2.4 `backend/routers/gateway.py`

**Goal:** Expose settings via REST so the new Settings page can
read/write them.

```python
class GatewaySettingsRequest(BaseModel):
    url: str
    token: str

@router.get("/settings")
async def get_gateway_settings():
    persisted = load_gateway_settings()
    return {
        "url": settings.gateway_url,
        "token_configured": bool(settings.gateway_token),
        "token_preview": (settings.gateway_token[:8] + "...")
                         if settings.gateway_token and len(settings.gateway_token) > 8 else "",
        "source": "persisted" if persisted.get("gateway_url") == settings.gateway_url
                  else "env" if (settings.gateway_url and not persisted.get("gateway_url"))
                  else "auto",
    }

@router.put("/settings")
async def update_gateway_settings(req: GatewaySettingsRequest):
    try:
        await gateway.update_gateway_settings(req.url, req.token)
        return {"ok": True, "url": settings.gateway_url,
                "token_configured": bool(settings.gateway_token),
                "message": "Gateway settings updated. Reconnecting..."}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

Note: token value itself is **never** returned to the frontend — only
a preview (first 8 chars) and a boolean. PUT body is JSON over
HTTPS in deployment.

---

## 2.5 `frontend/src/pages/Settings.tsx`

**Goal:** Replace the placeholder with a real settings page.

Features:
- Live status header with green / amber / red dot, polling
  `/api/gateway/status` every 5 s.
- URL input + Token input (with show/hide eye icon).
- "Save & Reconnect" → `PUT /api/gateway/settings`.
- "Reconnect" → triggers reconnection without changing settings.
- Token preview (first 8 chars) and source badge (env / persisted / auto).
- Diagnostics block: device id, has identity, has operator token,
  scopes, gateway auth mode, auth error.
- Quick Setup Guide listing the 4 steps.

Fetch hooks (excerpt):

```tsx
const fetchSettings = useCallback(async () => {
  const res = await fetch('/api/gateway/settings')
  setSettings(await res.json())
}, [])

useEffect(() => {
  fetchSettings(); fetchDiagnostics()
  const i = setInterval(fetchDiagnostics, 5000)
  return () => clearInterval(i)
}, [fetchSettings, fetchDiagnostics])
```

Save handler hits PUT and re-fetches both endpoints.

---

## 2.6 `start.sh`

**Goal:** Auto-start a known-good local OpenClaw gateway so MC works
out of the box; degrade gracefully when no binary is installed.

Key blocks:

```bash
export OPENCLAW_HOME="${OPENCLAW_HOME:-/tmp/oc-home}"
```

We use `/tmp/oc-home` instead of `~/.openclaw` to keep the sandbox
gateway state isolated from any user install.

Binary discovery (prefers v2026.4.25):

```bash
for p in \
    "$(dirname $0)/../.oc-v25/node_modules/.bin/openclaw" \
    /data/users/LJTvWmv8w3YZfYb6dMwkwprDPJv1/Workspace/.oc-v25/node_modules/.bin/openclaw \
    "$(dirname $0)/../.openclaw-install/node_modules/.bin/openclaw"; do
    [ -x "$p" ] && OPENCLAW_BIN="$p" && break
done
```

Fresh-config bootstrap (only if missing) — note especially
`pricing.bootstrap: false` and `plugins.deny` for bonjour:

```json
{
  "gateway": {
    "mode": "local",
    "bind": "loopback",
    "auth": { "mode": "token", "token": "<random hex>" },
    "pricing": { "bootstrap": false }
  },
  "models": { "mode": "merge", "providers": {} },
  "agents": { "list": [{ "id": "dev", "default": true,
              "identity": { "name": "Dev Agent", "theme": "assistant", "emoji": "🤖" }}] },
  "plugins": { "deny": ["bonjour", "phone-control", "talk-voice"], "entries": {} }
}
```

Gateway launch:

```bash
OPENCLAW_HOME="$OPENCLAW_HOME" OPENCLAW_DISABLE_BONJOUR=1 \
    $OPENCLAW_BIN gateway run --bind loopback --port 18789 \
                  --allow-unconfigured --verbose &
```

Why each flag:
- `--bind loopback` — only listen on 127.0.0.1
- `--port 18789` — well-known OC port
- `--allow-unconfigured` — skip the onboarding wizard requirement
- `--verbose` — without this v2026.4.25 was dying silently in the
  sandbox; verbose surfaces the real error.

Then `for i in $(seq 1 60)` waits up to 60 s for the port to open
(in practice it takes ~40 s on first run because of plugin loading).

If the binary isn't found we print an install hint and continue —
backend boots and the user can configure a remote gateway via
Settings.

---

## 2.7 `tasks.json`

Status updates only — marked the gateway-connection and Settings UI
tasks `completed`. No code impact.

---

## 2.8 What we did **not** change

- Phase 1–4 feature code (`tasks/`, `projects/`, `debate/`,
  `memory/`, `office/`, `autopilot/`, `skills/`, `aegis/`,
  `cost/`).
- `backend/main.py` mounts and middleware.
- The frontend router or layout.
- The Render deployment config.

These all continue to work as before. The only behaviour change is
where the gateway connection comes from.
