"""SSE event stream and compatibility status endpoints."""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from database import get_db
from services.runtime_registry import runtime_registry
from services.sse_broadcaster import sse

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
async def gateway_status_compat():
    """Compatibility status for older gateway-shaped frontend callers."""
    db = await get_db()
    runtime = await runtime_registry.status(db)
    return {
        "connected": runtime["ready"],
        "auth_status": runtime["active_runtime"],
        "server": {"runtime": runtime["active_runtime"]},
        "runtime": runtime,
    }


@router.get("/api/gateway/health")
async def gateway_health_compat():
    """Compatibility health check backed by the active runtime."""
    db = await get_db()
    runtime = await runtime_registry.status(db)
    return {"status": "ok" if runtime["ready"] else "error", "runtime": runtime}


@router.get("/api/gateway/models")
async def gateway_models_compat():
    """Compatibility models endpoint backed by model configs."""
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM model_configs ORDER BY purpose")
    return [dict(row) for row in rows]


@router.get("/api/gateway/sessions")
async def gateway_sessions_compat():
    """Compatibility sessions endpoint backed by native sessions."""
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM sessions ORDER BY created_at DESC LIMIT 100")
    return [dict(row) for row in rows]
