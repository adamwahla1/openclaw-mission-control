"""WebSocket operator client connecting to OpenClaw Gateway.

Maintains a persistent WS connection, handles the handshake protocol,
subscribes to events, and bridges them to the SSE broadcaster.
"""
import asyncio
import json
import logging
import uuid
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from config import settings
from services.sse_broadcaster import sse

logger = logging.getLogger(__name__)


class GatewayBridge:
    def __init__(self):
        self._ws: Any = None
        self._connected = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 30
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._task: asyncio.Task | None = None
        self._features: dict = {}
        self._server_info: dict = {}

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def server_info(self) -> dict:
        return self._server_info

    async def start(self):
        """Start the gateway connection loop."""
        self._task = asyncio.create_task(self._connection_loop())

    async def stop(self):
        """Stop the gateway connection."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._connected = False

    async def _connection_loop(self):
        """Reconnect loop with exponential backoff."""
        while True:
            try:
                if not settings.gateway_url or not settings.gateway_token:
                    logger.info("Gateway URL/token not configured, waiting...")
                    await asyncio.sleep(5)
                    continue

                logger.info(f"Connecting to gateway: {settings.gateway_url}")
                async with websockets.connect(
                    settings.gateway_url,
                    max_size=26_214_400,  # 25MB
                    ping_interval=15,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    await self._handshake(ws)
                    self._connected = True
                    self._reconnect_delay = 1
                    logger.info("Gateway connected successfully")

                    await sse.broadcast("gateway", {"status": "connected", "server": self._server_info})

                    # Listen for events
                    async for raw in ws:
                        try:
                            frame = json.loads(raw)
                            await self._handle_frame(frame)
                        except json.JSONDecodeError:
                            logger.warning("Received non-JSON frame from gateway")

            except ConnectionClosed as e:
                logger.warning(f"Gateway connection closed: {e}")
            except ConnectionRefusedError:
                logger.warning("Gateway connection refused")
            except Exception as e:
                logger.error(f"Gateway error: {e}")
            finally:
                self._connected = False
                self._ws = None
                await sse.broadcast("gateway", {"status": "disconnected"})

            # Backoff
            logger.info(f"Reconnecting in {self._reconnect_delay}s...")
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

    async def _handshake(self, ws):
        """Perform the connect handshake per OpenClaw Gateway protocol."""
        # Wait for connect.challenge
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        challenge = json.loads(raw)

        if challenge.get("event") != "connect.challenge":
            # Some gateways may not send challenge — proceed directly
            logger.info("No challenge received, sending connect directly")
        
        # Send connect request
        connect_id = str(uuid.uuid4())
        connect_req = {
            "type": "req",
            "id": connect_id,
            "method": "connect",
            "params": {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {
                    "id": "mission-control",
                    "version": "0.1.0",
                    "platform": "web",
                    "mode": "operator",
                },
                "role": "operator",
                "scopes": ["operator.read", "operator.write"],
                "caps": [],
                "commands": [],
                "permissions": {},
                "auth": {"token": settings.gateway_token},
                "locale": "en-US",
                "userAgent": "openclaw-mission-control/0.1.0",
            },
        }
        await ws.send(json.dumps(connect_req))

        # Wait for hello-ok response
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        res = json.loads(raw)

        if res.get("type") == "res" and res.get("ok"):
            payload = res.get("payload", {})
            self._server_info = payload.get("server", {})
            self._features = payload.get("features", {})
            logger.info(f"Handshake OK — server: {self._server_info}")
        else:
            error = res.get("error", {})
            raise ConnectionError(f"Handshake failed: {error}")

    async def _handle_frame(self, frame: dict):
        """Route incoming gateway frames."""
        frame_type = frame.get("type")

        if frame_type == "res":
            # Response to a pending RPC request
            req_id = frame.get("id")
            if req_id and req_id in self._pending_requests:
                self._pending_requests[req_id].set_result(frame)
        elif frame_type == "event":
            event = frame.get("event", "")
            payload = frame.get("payload", {})
            # Broadcast all gateway events to SSE subscribers
            await sse.broadcast(f"gw:{event}", payload)

    async def rpc(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
        """Send an RPC request to the gateway and await response."""
        if not self._ws or not self._connected:
            raise ConnectionError("Gateway not connected")

        req_id = str(uuid.uuid4())
        req = {
            "type": "req",
            "id": req_id,
            "method": method,
        }
        if params:
            req["params"] = params

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[req_id] = future

        try:
            await self._ws.send(json.dumps(req))
            res = await asyncio.wait_for(future, timeout=timeout)

            if res.get("ok"):
                return res.get("payload", {})
            else:
                error = res.get("error", {})
                raise Exception(f"Gateway RPC error ({method}): {error}")
        finally:
            self._pending_requests.pop(req_id, None)

    # --- Convenience methods ---

    async def list_agents(self) -> list:
        result = await self.rpc("agents.list")
        return result if isinstance(result, list) else result.get("agents", [])

    async def create_agent(self, name: str, role: str, soul_config: dict | None = None) -> dict:
        params = {"name": name, "role": role}
        if soul_config:
            params["soul"] = soul_config
        return await self.rpc("agents.create", params)

    async def list_sessions(self) -> list:
        result = await self.rpc("sessions.list")
        return result if isinstance(result, list) else result.get("sessions", [])

    async def create_session(self, agent_id: str | None = None, task_id: str | None = None) -> dict:
        params = {}
        if agent_id:
            params["agentId"] = agent_id
        if task_id:
            params["taskId"] = task_id
        return await self.rpc("sessions.create", params)

    async def send_message(self, session_id: str, content: str) -> dict:
        return await self.rpc("sessions.send", {
            "sessionId": session_id,
            "message": content,
        })

    async def list_models(self) -> list:
        result = await self.rpc("models.list")
        return result if isinstance(result, list) else result.get("models", [])

    async def get_health(self) -> dict:
        return await self.rpc("health")

    async def get_status(self) -> dict:
        return await self.rpc("status")


# Singleton
gateway = GatewayBridge()
