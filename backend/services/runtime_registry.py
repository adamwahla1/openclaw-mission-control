"""Runtime registry for native-first Mission Control."""
from __future__ import annotations

import logging
from typing import Any

import aiosqlite

from services.native_runtime import native_runtime
from services.sse_broadcaster import sse

logger = logging.getLogger(__name__)


class OpenClawRuntimeAdapter:
    name = "openclaw"
    label = "OpenClaw Gateway"

    def __init__(self) -> None:
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        try:
            from services.gateway_bridge import gateway

            await gateway.start()
            self._started = True
        except Exception as exc:
            logger.warning("OpenClaw runtime failed to start: %s", exc)

    async def stop(self) -> None:
        if not self._started:
            return
        try:
            from services.gateway_bridge import gateway

            await gateway.stop()
        finally:
            self._started = False

    async def status(self, db: aiosqlite.Connection) -> dict[str, Any]:
        try:
            from services.gateway_bridge import gateway

            return {
                "name": self.name,
                "label": self.label,
                "ready": gateway.connected,
                "connected": gateway.connected,
                "authenticated": gateway.authenticated,
                "auth_status": gateway.auth_status,
                "server": gateway.server_info,
                "optional": True,
            }
        except Exception as exc:
            return {
                "name": self.name,
                "label": self.label,
                "ready": False,
                "optional": True,
                "error": str(exc),
            }


class RuntimeRegistry:
    def __init__(self) -> None:
        self.native = native_runtime
        self.openclaw = OpenClawRuntimeAdapter()
        self._active = "native"

    async def start(self, db: aiosqlite.Connection) -> None:
        self._active = await self._load_active(db)
        if self._active == "openclaw":
            await self.openclaw.start()
        await sse.broadcast("runtime", {"status": "ready", "active_runtime": self._active})

    async def stop(self) -> None:
        await self.openclaw.stop()

    async def _load_active(self, db: aiosqlite.Connection) -> str:
        async with db.execute("SELECT value FROM runtime_config WHERE key = 'active_runtime'") as cursor:
            row = await cursor.fetchone()
        value = row["value"] if row else "native"
        return value if value in {"native", "openclaw"} else "native"

    async def set_active(self, db: aiosqlite.Connection, runtime_name: str) -> dict[str, Any]:
        if runtime_name not in {"native", "openclaw"}:
            raise ValueError("runtime must be 'native' or 'openclaw'")
        if runtime_name == "openclaw":
            await self.openclaw.start()
        elif self._active == "openclaw":
            await self.openclaw.stop()
        self._active = runtime_name
        await db.execute(
            """
            INSERT INTO runtime_config (key, value, updated_at)
            VALUES ('active_runtime', ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
            """,
            (runtime_name,),
        )
        await db.commit()
        status = await self.status(db)
        await sse.broadcast("runtime", {"status": "active_changed", "active_runtime": runtime_name})
        return status

    async def status(self, db: aiosqlite.Connection) -> dict[str, Any]:
        self._active = await self._load_active(db)
        native_status = await self.native.status(db)
        openclaw_status = await self.openclaw.status(db)
        active_status = native_status if self._active == "native" else openclaw_status
        return {
            "active_runtime": self._active,
            "ready": bool(active_status.get("ready")),
            "supervision": "supervised",
            "runtimes": [native_status, openclaw_status],
        }

    def active_runtime(self):
        return self.openclaw if self._active == "openclaw" else self.native


runtime_registry = RuntimeRegistry()
