"""Gateway diagnostics, device auth management, and settings router."""
from fastapi import APIRouter
from pydantic import BaseModel

from config import settings, save_gateway_settings, load_gateway_settings
from services.gateway_bridge import gateway
from services.device_auth import device_auth

router = APIRouter(prefix="/api/gateway", tags=["gateway"])


# ── Settings Models ──────────────────────────────────────────────────────────

class GatewaySettingsRequest(BaseModel):
    url: str
    token: str


# ── Settings Endpoints ───────────────────────────────────────────────────────

@router.get("/settings")
async def get_gateway_settings():
    """Get current gateway URL and token configuration."""
    persisted = load_gateway_settings()
    return {
        "url": settings.gateway_url,
        "token_configured": bool(settings.gateway_token),
        "token_preview": settings.gateway_token[:8] + "..." if settings.gateway_token and len(settings.gateway_token) > 8 else "",
        "source": "persisted" if persisted.get("gateway_url") == settings.gateway_url else "env" if (settings.gateway_url and not persisted.get("gateway_url")) else "auto",
    }


@router.put("/settings")
async def update_gateway_settings(req: GatewaySettingsRequest):
    """Update gateway URL and token, then trigger reconnection."""
    try:
        await gateway.update_gateway_settings(req.url, req.token)
        return {
            "ok": True,
            "url": settings.gateway_url,
            "token_configured": bool(settings.gateway_token),
            "message": "Gateway settings updated. Reconnecting...",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Status & Diagnostics ─────────────────────────────────────────────────────


@router.get("/status")
async def gateway_status():
    """Full gateway connection and auth status."""
    return gateway.get_diagnostics()


@router.get("/device")
async def device_info():
    """Current device identity and auth state."""
    return device_auth.status()


@router.post("/pairing/approve/{request_id}")
async def approve_pairing(request_id: str):
    """Approve a pending device pairing request."""
    if not gateway.connected:
        return {"ok": False, "error": "Gateway not connected"}
    try:
        result = await gateway.approve_pairing(request_id)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/pairing/reject/{request_id}")
async def reject_pairing(request_id: str):
    """Reject a pending device pairing request."""
    if not gateway.connected:
        return {"ok": False, "error": "Gateway not connected"}
    try:
        result = await gateway.reject_pairing(request_id)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/pairing/pending")
async def pending_pairings():
    """List pending device pairing requests."""
    if not gateway.connected:
        return {"ok": False, "error": "Gateway not connected", "pairings": []}
    try:
        result = await gateway.list_pending_pairings()
        return {"ok": True, "pairings": result}
    except Exception as e:
        return {"ok": False, "error": str(e), "pairings": []}


@router.post("/reconnect")
async def reconnect_gateway():
    """Force a gateway reconnection (useful after pairing approval)."""
    return {
        "ok": True,
        "message": "Reconnection will happen automatically",
        "current_status": gateway.get_diagnostics(),
    }


@router.get("/agents")
async def gateway_agents():
    """List agents from the gateway (live)."""
    if not gateway.connected:
        return {"ok": False, "error": "Gateway not connected", "agents": []}
    try:
        agents = await gateway.list_agents()
        return {"ok": True, "agents": agents}
    except Exception as e:
        return {"ok": False, "error": str(e), "agents": []}


@router.get("/status-rpc")
async def gateway_status_rpc():
    """Get live gateway status via RPC."""
    if not gateway.connected:
        return {"ok": False, "error": "Gateway not connected"}
    try:
        result = await gateway.get_status()
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}
