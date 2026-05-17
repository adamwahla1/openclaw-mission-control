"""Orchestrator HTTP endpoints."""
import json
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db
from services import orchestrator
from services.agent_factory import create_agent_for_task

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])


class DispatchRequest(BaseModel):
    task_id: str


class FactoryRequest(BaseModel):
    role: Optional[str] = None
    title: str
    description: Optional[str] = None
    tags: list[str] = []
    priority: str = "medium"


@router.post("/dispatch")
async def dispatch_task(body: DispatchRequest):
    """Dispatch a task into the native Project Builder runtime."""
    try:
        result = await orchestrator.dispatch(body.task_id)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Dispatch failed: {e}")


@router.get("/status/{task_id}")
async def get_dispatch_status(task_id: str):
    """Get orchestration status for a task."""
    db = await get_db()
    async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Task not found")

    task = dict(row)
    task["tags"] = json.loads(task.get("tags", "[]"))

    async with db.execute(
        "SELECT COUNT(*) as cnt FROM task_messages WHERE task_id = ?", (task_id,)
    ) as cursor:
        msg_count = (await cursor.fetchone())["cnt"]

    async with db.execute(
        "SELECT COUNT(*) as cnt FROM tasks WHERE parent_task_id = ?", (task_id,)
    ) as cursor:
        subtask_count = (await cursor.fetchone())["cnt"]

    run = None
    if task.get("gateway_session_id"):
        async with db.execute("SELECT * FROM runs WHERE id = ?", (task["gateway_session_id"],)) as cursor:
            run_row = await cursor.fetchone()
        run = dict(run_row) if run_row else None

    active = task_id in orchestrator._active_dispatches or (run and run.get("status") in {"queued", "running", "awaiting_approval"})

    return {
        "task_id": task_id,
        "status": task["status"],
        "assigned_agent_id": task.get("assigned_agent_id"),
        "session_id": task.get("gateway_session_id"),
        "run_id": task.get("gateway_session_id"),
        "run_status": run.get("status") if run else None,
        "current_step": run.get("current_step") if run else None,
        "message_count": msg_count,
        "subtask_count": subtask_count,
        "dispatch_active": bool(active),
    }


@router.post("/agents/factory")
async def run_agent_factory(body: FactoryRequest):
    """Manually trigger the native Agent Factory to create an agent."""
    task_context = {
        "title": body.title,
        "description": body.description,
        "tags": body.tags,
        "priority": body.priority,
    }
    try:
        agent = await create_agent_for_task(task_context, role=body.role)
        return agent
    except Exception as e:
        raise HTTPException(500, f"Agent Factory failed: {e}")
