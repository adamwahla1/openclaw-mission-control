import json
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenClaw Gateway — set MC_GATEWAY_URL / MC_GATEWAY_TOKEN for remote connection
    # Falls back to auto-detection from local OpenClaw config
    gateway_url: str = ""  # e.g. wss://your-machine.tail12345.ts.net:18789
    gateway_token: str = ""  # Gateway auth token

    # Also accept OPENCLAW_GATEWAY_URL / OPENCLAW_GATEWAY_TOKEN (common convention)
    # Handled in post-init below

    # Server
    host: str = "0.0.0.0"
    port: int = 3100  # Will be overridden by APP_PORT + 100
    cors_origins: list[str] = ["*"]

    # Database
    db_path: str = os.path.join(os.path.dirname(__file__), ".data", "mission_control.db")

    class Config:
        env_prefix = "MC_"


settings = Settings()

# Override port from APP_PORT if available
app_port = os.environ.get("APP_PORT", "3000")
settings.port = int(app_port) + 100

# ── Gateway URL / Token Resolution ──────────────────────────────────────────
# Priority:
#   1. MC_GATEWAY_URL / MC_GATEWAY_TOKEN (pydantic env vars)
#   2. OPENCLAW_GATEWAY_URL / OPENCLAW_GATEWAY_TOKEN (convention from reference MCs)
#   3. Auto-detect from local OpenClaw config (~/.openclaw/openclaw.json)
#   4. Default to ws://127.0.0.1:18789

if not settings.gateway_url:
    settings.gateway_url = os.environ.get("OPENCLAW_GATEWAY_URL", "")

if not settings.gateway_token:
    settings.gateway_token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

# Auto-detect from local OpenClaw config if still empty
if not settings.gateway_url or not settings.gateway_token:
    try:
        _oc_home = os.environ.get("OPENCLAW_HOME", "")

        _search_paths = []
        if _oc_home:
            _search_paths.append(os.path.join(_oc_home, ".openclaw", "openclaw.json"))
            _search_paths.append(os.path.join(_oc_home, "openclaw.json"))
        _search_paths.append(os.path.expanduser("~/.openclaw/openclaw.json"))

        _oc_config = None
        for _p in _search_paths:
            if os.path.exists(_p):
                with open(_p) as _f:
                    _oc_config = json.load(_f)
                break

        if _oc_config:
            _gw = _oc_config.get("gateway", {})

            if not settings.gateway_url:
                settings.gateway_url = "ws://127.0.0.1:18789"

            if not settings.gateway_token:
                settings.gateway_token = _gw.get("auth", {}).get("token", "")
    except Exception:
        pass

# Ensure gateway_url has a default for local dev
if not settings.gateway_url:
    settings.gateway_url = "ws://127.0.0.1:18789"


def save_gateway_settings(url: str, token: str) -> None:
    """Persist gateway settings to a local config file so they survive restarts."""
    config_dir = Path.home() / ".mission-control"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "gateway.json"
    data = {}
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text())
        except Exception:
            pass
    data["gateway_url"] = url
    data["gateway_token"] = token
    config_file.write_text(json.dumps(data, indent=2))
    # Update runtime settings
    settings.gateway_url = url
    settings.gateway_token = token


def load_gateway_settings() -> dict:
    """Load persisted gateway settings from local config file."""
    config_file = Path.home() / ".mission-control" / "gateway.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text())
        except Exception:
            pass
    return {}


# On startup, load persisted settings if env vars aren't set
_persisted = load_gateway_settings()
if _persisted:
    if not os.environ.get("MC_GATEWAY_URL") and not os.environ.get("OPENCLAW_GATEWAY_URL"):
        if _persisted.get("gateway_url"):
            settings.gateway_url = _persisted["gateway_url"]
    if not os.environ.get("MC_GATEWAY_TOKEN") and not os.environ.get("OPENCLAW_GATEWAY_TOKEN"):
        if _persisted.get("gateway_token"):
            settings.gateway_token = _persisted["gateway_token"]
