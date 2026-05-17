"""Runtime selection and status endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db
from services.runtime_registry import runtime_registry

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


class ActiveRuntimeRequest(BaseModel):
    runtime: str


@router.get("/status")
async def runtime_status():
    db = await get_db()
    return await runtime_registry.status(db)


@router.put("/active")
async def set_active_runtime(body: ActiveRuntimeRequest):
    db = await get_db()
    try:
        return await runtime_registry.set_active(db, body.runtime)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
