"""Gateway diagnostics and device auth management router."""
from fastapi import APIRouter

from services.gateway_bridge import gateway
from services.device_auth import device_auth

router = APIRouter(prefix="/api/gateway", tags=["gateway"])


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
