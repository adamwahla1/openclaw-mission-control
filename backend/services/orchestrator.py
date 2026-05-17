"""Orchestrator service - dispatches tasks into the native Mission Control runtime."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Callable

from database import get_db
from services.agent_factory import create_agent_for_task
from services.runtime_registry import runtime_registry
from services.sse_broadcaster import sse

logger = logging.getLogger(__name__)

_active_dispatches: dict[str, asyncio.Task] = {}
_event_handlers: dict[str, list[Callable]] = {}


def on_gateway_event(event: str, handler):
    """Compatibility hook for old callers that registered orchestrator events."""
    _event_handlers.setdefault(event, []).append(handler)


def off_gateway_event(event: str, handler):
    """Unregister a compatibility event callback."""
    if handler in _event_handlers.get(event, []):
        _event_handlers[event].remove(handler)


async def _fire_event(event: str, payload: dict):
    for handler in _event_handlers.get(event, []):
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(payload)
            else:
                handler(payload)
        except Exception as exc:
            logger.error("Orchestrator event handler error (%s): %s", event, exc)


def _decompose_task(task: dict) -> list[dict]:
    """Heuristic task decomposition. Caller persists returned subtasks."""
    description = task.get("description", "") or ""
    tags = task.get("tags", [])
    priority = task.get("priority", "medium")
    title = task.get("title", "")

    should_decompose = len(description) > 300 or len(tags) >= 3 or priority == "critical"
    if not should_decompose:
        return []

    text_lower = f"{title} {description}".lower()
    if any(kw in text_lower for kw in ["research", "analyze", "investigate"]):
        return [
            {"title": f"Research: {title}", "description": "Gather information and sources"},
            {"title": f"Analyze: {title}", "description": "Synthesize findings and identify patterns"},
            {"title": f"Report: {title}", "description": "Produce final summary and recommendations"},
        ]
    if any(kw in text_lower for kw in ["build", "implement", "develop", "code"]):
        return [
            {"title": f"Plan: {title}", "description": "Design approach and architecture"},
            {"title": f"Implement: {title}", "description": "Draft the implementation"},
            {"title": f"Review & Test: {title}", "description": "Validate implementation"},
        ]
    if any(kw in text_lower for kw in ["write", "draft", "document"]):
        return [
            {"title": f"Outline: {title}", "description": "Create structure and outline"},
            {"title": f"Draft: {title}", "description": "Write initial content"},
            {"title": f"Edit & Polish: {title}", "description": "Refine and finalize"},
        ]
    return [
        {"title": f"Setup: {title}", "description": "Prepare resources and context"},
        {"title": f"Execute: {title}", "description": "Carry out the main work"},
        {"title": f"Finalize: {title}", "description": "Review and deliver outputs"},
    ]


def _build_initial_prompt(task: dict, agent: dict) -> str:
    title = task.get("title", "")
    description = task.get("description", "") or ""
    priority = task.get("priority", "medium")
    tags = task.get("tags", [])
    tag_line = f"\nTags: {', '.join(tags)}" if tags else ""
    detail_line = f"\nDetails: {description}" if description else ""
    return f"""Task Assignment

Task: {title}
Priority: {priority.upper()}{tag_line}{detail_line}

Assigned native agent: {agent.get('name')} ({agent.get('role')})

Run this through Mission Control Project Builder:
1. Confirm understanding.
2. Produce a plan.
3. Research local context.
4. Draft the build strategy.
5. Pause for approval before write-level work.
6. Review, validate, and report.
"""


async def _persist_message(
    task_id: str,
    session_id: str | None,
    role: str,
    content: str,
    agent: dict | None = None,
) -> dict:
    db = await get_db()
    msg_id = str(uuid.uuid4())
    agent_id = agent.get("id") if agent else None
    agent_name = agent.get("name") if agent else None

    await db.execute(
        """INSERT INTO task_messages
           (id, task_id, session_id, role, content, agent_id, agent_name)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (msg_id, task_id, session_id, role, content, agent_id, agent_name),
    )
    await db.commit()

    msg = {
        "id": msg_id,
        "task_id": task_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "tokens": None,
        "created_at": None,
    }
    await sse.broadcast("task.message", msg)
    return msg


async def dispatch(task_id: str) -> dict:
    """
    Dispatch a task to the native Project Builder runtime.

    OpenClaw is no longer required: the task gets a local agent, a native session,
    a durable run, and persisted run events that the UI can replay.
    """
    db = await get_db()

    async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise ValueError(f"Task {task_id} not found")

    task = dict(row)
    task["tags"] = json.loads(task.get("tags") or "[]")

    if task.get("gateway_session_id"):
        return {"ok": True, "message": "Task already dispatched", "task_id": task_id}
    if task_id in _active_dispatches:
        return {"ok": True, "message": "Dispatch already in progress", "task_id": task_id}

    _active_dispatches[task_id] = asyncio.current_task()  # visible to status endpoint during setup
    try:
        await db.execute(
            "UPDATE tasks SET status = 'assigned', updated_at = datetime('now') WHERE id = ?",
            (task_id,),
        )
        await db.commit()
        await sse.broadcast("task.updated", {**task, "status": "assigned"})

        subtasks = _decompose_task(task)
        for st in subtasks:
            await db.execute(
                """INSERT INTO tasks (id, title, description, parent_task_id, priority, tags, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'inbox')""",
                (
                    str(uuid.uuid4()),
                    st["title"],
                    st["description"],
                    task_id,
                    task["priority"],
                    json.dumps(task.get("tags", [])),
                ),
            )
        if subtasks:
            await db.commit()
            await sse.broadcast("task.subtasks_created", {"task_id": task_id, "count": len(subtasks)})

        await _persist_message(
            task_id,
            None,
            "orchestrator",
            f"Task dispatched to Mission Control native runtime. Specialist agent is being prepared. Subtasks: {len(subtasks)}.",
        )

        agent = await create_agent_for_task(task)
        initial_prompt = _build_initial_prompt(task, agent)
        session = await runtime_registry.native.start_session(
            db,
            title=f"Task: {task.get('title', 'Untitled')}",
            agent_id=agent["id"],
            task_id=task_id,
            metadata={"source": "orchestrator.dispatch"},
        )
        run = await runtime_registry.native.start_run(
            db,
            run_type="project_builder",
            title=f"Project Builder: {task.get('title', 'Untitled')}",
            objective=initial_prompt,
            task_id=task_id,
            session_id=session["id"],
            metadata={"agent_id": agent["id"], "source": "task.dispatch"},
        )

        await db.execute(
            """
            INSERT INTO messages (id, session_id, run_id, agent_id, role, content)
            VALUES (?, ?, ?, ?, 'user', ?)
            """,
            (str(uuid.uuid4()), session["id"], run["id"], agent["id"], initial_prompt),
        )
        await db.execute(
            """
            UPDATE tasks
            SET assigned_agent_id = ?, gateway_session_id = ?, status = 'in_progress', updated_at = datetime('now')
            WHERE id = ?
            """,
            (agent["id"], run["id"], task_id),
        )
        await db.commit()

        await _persist_message(task_id, run["id"], "orchestrator", initial_prompt, agent)
        await sse.broadcast(
            "task.updated",
            {**task, "status": "in_progress", "assigned_agent_id": agent["id"], "gateway_session_id": run["id"]},
        )
        await _fire_event("run.started", {"task_id": task_id, "run_id": run["id"]})

        return {
            "ok": True,
            "message": f"Task dispatched to native Project Builder with {agent['name']}",
            "task_id": task_id,
            "agent_id": agent["id"],
            "agent_name": agent["name"],
            "session_id": session["id"],
            "run_id": run["id"],
            "subtasks_created": len(subtasks),
        }
    finally:
        _active_dispatches.pop(task_id, None)
