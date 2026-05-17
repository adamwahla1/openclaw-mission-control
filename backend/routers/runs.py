"""Native run and event ledger endpoints."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db
from services.runtime_registry import runtime_registry

router = APIRouter(prefix="/api/runs", tags=["runs"])


class RunCreateRequest(BaseModel):
    run_type: str = "project_builder"
    title: str = "Project Builder Run"
    objective: str
    task_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = {}


@router.get("")
async def list_runs(status: str | None = None, limit: int = 50):
    db = await get_db()
    runtime = runtime_registry.native
    return await runtime.list_runs(db, status=status, limit=limit)


@router.post("", status_code=201)
async def create_run(body: RunCreateRequest):
    db = await get_db()
    runtime = runtime_registry.native
    return await runtime.start_run(
        db,
        run_type=body.run_type,
        title=body.title,
        objective=body.objective,
        task_id=body.task_id,
        session_id=body.session_id,
        metadata=body.metadata,
    )


@router.get("/{run_id}")
async def get_run(run_id: str):
    db = await get_db()
    try:
        return await runtime_registry.native.get_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/{run_id}/events")
async def get_run_events(run_id: str):
    db = await get_db()
    return await runtime_registry.native.get_events(db, run_id)


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: str):
    db = await get_db()
    try:
        return await runtime_registry.native.cancel_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/{run_id}/resume")
async def resume_run(run_id: str):
    db = await get_db()
    try:
        return await runtime_registry.native.resume_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
