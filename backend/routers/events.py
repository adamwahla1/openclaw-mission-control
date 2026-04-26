"""SSE event stream + gateway status endpoints."""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from services.sse_broadcaster import sse
from services.gateway_bridge import gateway

router = APIRouter(tags=["events"])


@router.get("/events")
async def event_stream():
    """SSE endpoint for real-time frontend updates."""
    async def generate():
        async for data in sse.subscribe():
            yield data

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/gateway/status")
async def gateway_status():
    """Current gateway connection status."""
    return {
        "connected": gateway.connected,
        "server": gateway.server_info,
    }


@router.get("/api/gateway/health")
async def gateway_health():
    """Proxy gateway health check."""
    if not gateway.connected:
        return {"status": "disconnected"}
    try:
        return await gateway.get_health()
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/api/gateway/models")
async def gateway_models():
    """List models available via gateway."""
    if not gateway.connected:
        return []
    return await gateway.list_models()


@router.get("/api/gateway/sessions")
async def gateway_sessions():
    """List sessions from gateway."""
    if not gateway.connected:
        return []
    return await gateway.list_sessions()
