"""WebSocket operator client connecting to OpenClaw Gateway.

Implements the full device auth handshake:
  1. Open WS → receive connect.challenge (nonce)
  2. Sign v3 payload with Ed25519 device key
  3. Send connect message with device identity + signature
  4. Receive connect.ok (or error)

Maintains persistent connection, bridges events to SSE broadcaster,
and provides RPC convenience methods.
"""
import asyncio
import json
import logging
import uuid
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from config import settings
from services.device_auth import device_auth, DeviceAuthManager
from services.sse_broadcaster import sse

logger = logging.getLogger(__name__)


class GatewayBridge:
    def __init__(self):
        self._ws: Any = None
        self._connected = False
        self._auth_status: str = "none"  # none | challenged | authenticating | authenticated | paired | failed
        self._reconnect_delay = 1
        self._max_reconnect_delay = 30
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._task: asyncio.Task | None = None
        self._features: dict = {}
        self._server_info: dict = {}
        self._paired: bool = False
        self._pairing_pending: bool = False
        self._auth_error: str | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def authenticated(self) -> bool:
        return self._auth_status in ("authenticated", "paired")

    @property
    def auth_status(self) -> str:
        return self._auth_status

    @property
    def server_info(self) -> dict:
        return self._server_info

    @property
    def pairing_pending(self) -> bool:
        return self._pairing_pending

    async def start(self):
        """Start the gateway connection loop."""
        # Initialize device auth (load/generate identity)
        device_auth.initialize()
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

    def _get_gateway_url(self) -> str:
        """Resolve gateway URL from settings or device auth auto-discovery."""
        if settings.gateway_url:
            return settings.gateway_url
        return device_auth.get_gateway_url()

    async def _connection_loop(self):
        """Reconnect loop with exponential backoff."""
        while True:
            try:
                url = self._get_gateway_url()
                if not url:
                    logger.info("Gateway URL not configured, waiting...")
                    await asyncio.sleep(5)
                    continue

                logger.info(f"Connecting to gateway: {url}")
                async with websockets.connect(
                    url,
                    max_size=26_214_400,  # 25MB
                    ping_interval=15,
                    ping_timeout=10,
                    open_timeout=30,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    self._auth_status = "none"
                    await self._handshake(ws)
                    self._connected = True
                    self._reconnect_delay = 1
                    logger.info("Gateway connected and authenticated")

                    await sse.broadcast("gateway", {
                        "status": "connected",
                        "auth": self._auth_status,
                        "server": self._server_info,
                    })

                    # Listen for frames
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
            except ConnectionError as e:
                logger.error(f"Gateway handshake failed: {e}")
            except Exception as e:
                logger.error(f"Gateway error: {e}")
            finally:
                self._connected = False
                self._ws = None
                self._auth_status = "none"
                await sse.broadcast("gateway", {"status": "disconnected"})

            # Backoff
            logger.info(f"Reconnecting in {self._reconnect_delay}s...")
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * 2, self._max_reconnect_delay
            )

    async def _handshake(self, ws):
        """Perform the full device auth handshake per OpenClaw Gateway Protocol v3.

        Flow:
          1. Wait for connect.challenge event (contains nonce)
          2. Build v3 signed connect message
          3. Send connect request
          4. Receive connect.ok or connect.error
        """
        self._auth_status = "challenged"
        nonce = ""

        # Step 1: Receive challenge
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            challenge = json.loads(raw)

            if challenge.get("type") == "event" and challenge.get("event") == "connect.challenge":
                nonce = challenge.get("payload", {}).get("nonce", "")
                logger.info(f"Received connect.challenge (nonce={nonce[:12]}...)")
            elif challenge.get("event") == "connect.challenge":
                nonce = challenge.get("payload", {}).get("nonce", "")
                logger.info(f"Received connect.challenge (nonce={nonce[:12]}...)")
            else:
                # Gateway didn't send a challenge — might be auth=none mode
                logger.info("No challenge received, attempting direct connect")
                nonce = ""
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for connect.challenge, proceeding without nonce")

        # Step 2: Build and send connect with device auth
        self._auth_status = "authenticating"

        # Determine auth tokens:
        # - Gateway shared token (from openclaw.json config)
        # - Device token (stored after pairing)
        # The signature payload's `token` field MUST match `auth.token` for
        # the server to verify the signature correctly. If a gateway shared
        # token exists, it takes priority as auth.token, and the device token
        # is sent separately as auth.deviceToken (for scope/identity lookup).
        gw_token = device_auth.get_gateway_token() or settings.gateway_token
        device_token = device_auth.operator_token

        if gw_token:
            # Gateway has a shared token — sign with it, send device token separately
            auth_token_for_signature = gw_token
            auth_dict = {"token": gw_token, "deviceToken": device_token} if device_token else {"token": gw_token}
        elif device_token:
            # No shared token — use device token for both signature and auth
            auth_token_for_signature = device_token
            auth_dict = {"token": device_token}
        else:
            # No tokens at all
            auth_token_for_signature = ""
            auth_dict = None

        # Build connect message with the correct token for the signature
        connect_msg = device_auth.build_connect(
            nonce=nonce,
            role="operator",
            scopes=["operator.read", "operator.write"],
            token_override=auth_token_for_signature,
        )

        # Set the auth object
        if auth_dict:
            connect_msg["params"]["auth"] = auth_dict

        logger.info(
            f"Connect: clientId=cli role=operator scopes={connect_msg['params']['scopes']} "
            f"auth={'token' if auth_dict else 'none'}"
        )

        await ws.send(json.dumps(connect_msg))
        logger.info("Sent connect message with device auth signature")

        # Step 3: Wait for response
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        res = json.loads(raw)

        if res.get("type") == "res" and res.get("ok"):
            payload = res.get("payload", {})
            self._server_info = payload.get("server", {})
            self._features = payload.get("features", {})

            # Store device token if provided
            auth_info = payload.get("auth", {})
            device_token = auth_info.get("deviceToken", "")
            granted_scopes = auth_info.get("scopes", [])

            if device_token:
                device_auth.update_operator_token(device_token, granted_scopes)
                self._auth_status = "authenticated"
                logger.info(f"Authenticated with device token (scopes: {granted_scopes})")
            else:
                self._auth_status = "authenticated"
                logger.info("Authenticated (no device token in response)")

            # Check pairing status
            if payload.get("paired", False):
                self._paired = True
                self._auth_status = "paired"

            self._pairing_pending = False
            self._auth_error = None

        elif res.get("type") == "res" and not res.get("ok"):
            error = res.get("error", {})
            error_code = ""
            error_reason = ""

            # Handle structured error (device auth errors)
            if isinstance(error, dict):
                error_code = error.get("details", {}).get("code", "")
                error_reason = error.get("details", {}).get("reason", "")
                approved_scopes = error.get("details", {}).get("approvedScopes", [])
                error_msg = error.get("message", str(error))
            else:
                approved_scopes = []
                error_msg = str(error)

            # Check for pairing-required / scope-upgrade error
            # If the server tells us what scopes are approved, retry with those
            if (error_code in ("PAIRING_REQUIRED", "DEVICE_PAIRING_REQUIRED")
                    and approved_scopes):
                logger.warning(
                    f"Scope upgrade required — retrying with approved scopes: {approved_scopes}"
                )
                # Retry with approved scopes — use same token logic
                _gw_tok = device_auth.get_gateway_token() or settings.gateway_token
                _dev_tok = device_auth.operator_token
                if _gw_tok:
                    _sig_tok = _gw_tok
                    _auth_d = {"token": _gw_tok, "deviceToken": _dev_tok} if _dev_tok else {"token": _gw_tok}
                elif _dev_tok:
                    _sig_tok = _dev_tok
                    _auth_d = {"token": _dev_tok}
                else:
                    _sig_tok = ""
                    _auth_d = None

                retry_msg = device_auth.build_connect(
                    nonce=nonce,
                    role="operator",
                    scopes=approved_scopes,
                    token_override=_sig_tok,
                )
                if _auth_d:
                    retry_msg["params"]["auth"] = _auth_d

                await ws.send(json.dumps(retry_msg))

                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                retry_res = json.loads(raw)

                if retry_res.get("ok"):
                    payload = retry_res.get("payload", {})
                    self._server_info = payload.get("server", {})
                    auth_info = payload.get("auth", {})
                    if auth_info.get("deviceToken"):
                        device_auth.update_operator_token(
                            auth_info["deviceToken"],
                            auth_info.get("scopes", approved_scopes),
                        )
                    self._auth_status = "authenticated"
                    self._pairing_pending = True  # Still need scope upgrade approval
                    self._auth_error = f"Connected with limited scopes {approved_scopes}. Scope upgrade pending."
                    logger.info(f"Authenticated with limited scopes: {approved_scopes}")
                else:
                    self._auth_status = "failed"
                    self._auth_error = f"Retry with approved scopes failed: {retry_res.get('error')}"
                    raise ConnectionError(self._auth_error)

            elif "pairing" in error_msg.lower() or error_code == "DEVICE_PAIRING_REQUIRED":
                self._auth_status = "pairing_required"
                self._pairing_pending = True
                self._auth_error = error_msg
                logger.warning(f"Device pairing required: {error_msg}")
                # Don't raise — stay connected for pairing approval
            else:
                self._auth_status = "failed"
                self._auth_error = error_msg
                logger.error(f"Handshake failed: code={error_code} reason={error_reason} msg={error_msg}")
                raise ConnectionError(f"Handshake failed: {error_msg}")

        elif res.get("type") == "event" and res.get("event") == "connect.challenge":
            # Second challenge? Shouldn't happen but handle gracefully
            logger.warning("Received second challenge, re-sending connect")
            nonce2 = res.get("payload", {}).get("nonce", nonce)
            connect_msg2 = device_auth.build_connect(nonce=nonce2)
            await ws.send(json.dumps(connect_msg2))

        else:
            self._auth_status = "failed"
            self._auth_error = f"Unexpected handshake response: {res}"
            raise ConnectionError(f"Unexpected handshake response: {res}")

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

            # Handle pairing approval events
            if event == "pairing.approved":
                logger.info("Device pairing approved!")
                self._paired = True
                self._pairing_pending = False
                self._auth_status = "paired"
                if payload.get("deviceToken"):
                    device_auth.update_operator_token(
                        payload["deviceToken"],
                        payload.get("scopes", []),
                    )
                await sse.broadcast("gw:pairing.approved", payload)

            elif event == "pairing.rejected":
                logger.warning("Device pairing rejected")
                self._pairing_pending = False
                self._auth_status = "failed"
                await sse.broadcast("gw:pairing.rejected", payload)

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
        if isinstance(result, list):
            return result
        return result.get("agents", [])

    async def create_agent(self, name: str, role: str, soul_config: dict | None = None) -> dict:
        params = {"name": name, "role": role}
        if soul_config:
            params["soul"] = soul_config
        return await self.rpc("agents.create", params)

    async def list_sessions(self) -> list:
        result = await self.rpc("sessions.list")
        if isinstance(result, list):
            return result
        return result.get("sessions", [])

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
        if isinstance(result, list):
            return result
        return result.get("models", [])

    async def list_channels(self) -> list:
        result = await self.rpc("channels.list")
        if isinstance(result, list):
            return result
        return result.get("channels", [])

    async def get_health(self) -> dict:
        return await self.rpc("health")

    async def get_status(self) -> dict:
        return await self.rpc("status")

    async def approve_pairing(self, request_id: str) -> dict:
        """Approve a pending device pairing request."""
        return await self.rpc("approvals.pair", {
            "requestId": request_id,
            "action": "approve",
        })

    async def reject_pairing(self, request_id: str) -> dict:
        """Reject a pending device pairing request."""
        return await self.rpc("approvals.pair", {
            "requestId": request_id,
            "action": "reject",
        })

    async def list_pending_pairings(self) -> list:
        """List pending device pairing requests."""
        try:
            result = await self.rpc("approvals.list")
            if isinstance(result, list):
                return result
            return result.get("approvals", [])
        except Exception:
            return []

    async def chat(self, agent_id: str, message: str, session_id: str | None = None) -> dict:
        """Send a chat message to an agent."""
        params = {"agentId": agent_id, "message": message}
        if session_id:
            params["sessionId"] = session_id
        return await self.rpc("chat.send", params)

    def get_diagnostics(self) -> dict:
        """Return full gateway diagnostics."""
        return {
            "connected": self._connected,
            "auth_status": self._auth_status,
            "paired": self._paired,
            "pairing_pending": self._pairing_pending,
            "auth_error": self._auth_error,
            "server_info": self._server_info,
            "device_auth": device_auth.status(),
        }


# Singleton
gateway = GatewayBridge()
