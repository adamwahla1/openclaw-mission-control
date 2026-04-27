import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenClaw Gateway
    gateway_url: str = ""  # Auto-detected from ~/.openclaw/openclaw.json if empty
    gateway_token: str = ""  # Auto-detected from OpenClaw config if empty

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

# Auto-detect OpenClaw gateway URL and token from config
if not settings.gateway_url or not settings.gateway_token:
    try:
        import json as _json
        _oc_home = os.environ.get(
            "OPENCLAW_HOME",
            os.path.expanduser("~/.openclaw"),
        )
        # Auto-detect actual .openclaw location
        if not os.path.exists(os.path.join(_oc_home, "openclaw.json")):
            import glob
            for p in glob.glob("/data/users/*/.openclaw"):
                if os.path.exists(os.path.join(p, "openclaw.json")):
                    _oc_home = p
                    break

        _oc_config_path = os.path.join(_oc_home, "openclaw.json")
        if os.path.exists(_oc_config_path):
            with open(_oc_config_path) as _f:
                _oc_config = _json.load(_f)
            _gw = _oc_config.get("gateway", {})

            if not settings.gateway_url:
                _bind = _gw.get("bind", "loopback")
                if _bind == "loopback":
                    settings.gateway_url = "ws://127.0.0.1:18789"
                else:
                    settings.gateway_url = f"ws://127.0.0.1:18789"

            if not settings.gateway_token:
                settings.gateway_token = _gw.get("auth", {}).get("token", "")
    except Exception:
        pass
