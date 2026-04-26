import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenClaw Gateway
    gateway_url: str = "ws://localhost:18789"
    gateway_token: str = ""

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
