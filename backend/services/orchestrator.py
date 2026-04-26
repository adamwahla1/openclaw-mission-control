"""Orchestrator service — receives tasks, decomposes, dispatches agents."""
import asyncio
import json
import logging
import uuid

from database import get_db
from services.gateway_bridge import gateway
from services.sse_broadcaster import sse
from services.agent_factory import create_agent_for_task

logger = logging.getLogger(__name__)

# Active dispatch tasks: task_id → asyncio.Task
_active_dispatches: dict[str, asyncio.Task] = {}

# Gateway event callbacks: event_name → list of handlers
_event_handlers: dict[str, list] = {}


def on_gateway_event(event: str, handler):
    """Register a callback for a gateway event."""
    _event_handlers.setdefault(event, []).append(handler)


def off_gateway_event(event: str, handler):
    """Unregister a callback."""
    _event_handlers.get(event, []).remove(handler) if handler in _event_handlers.get(event, []) else None


async def _fire_event(event: str, payload: dict):
    """Invoke all registered handlers for a gateway event."""
    for handler in _event_handlers.get(event, []):
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(payload)
            else:
                handler(payload)
        except Exception as e:
            logger.error(f"Orchestrator event handler error ({event}): {e}")


def _decompose_task(task: dict) -> list[dict]:
    """
    Heuristic task decomposition.
    Returns list of subtask dicts (title, description) if task warrants decomposition.
    Does NOT create DB records — caller handles that.
    """
    subtasks = []
    description = task.get("description", "") or ""
    tags = task.get("tags", [])
    priority = task.get("priority", "medium")
    title = task.get("title", "")

    # Criteria: long description OR many tags OR critical priority
    should_decompose = (
        len(description) > 300
        or len(tags) >= 3
        or priority == "critical"
    )

    if not should_decompose:
        return []

    # Simple decomposition heuristic based on role type
    text_lower = (title + " " + description).lower()

    if any(kw in text_lower for kw in ["research", "analyze", "investigate"]):
        subtasks = [
            {"title": f"Research: {title}", "description": "Gather information and sources"},
            {"title": f"Analyze: {title}", "description": "Synthesize findings and identify patterns"},
            {"title": f"Report: {title}", "description": "Produce final summary and recommendations"},
        ]
    elif any(kw in text_lower for kw in ["build", "implement", "develop", "code"]):
        subtasks = [
            {"title": f"Plan: {title}", "description": "Design approach and architecture"},
            {"title": f"Implement: {title}", "description": "Write the code/solution"},
            {"title": f"Review & Test: {title}", "description": "Validate implementation"},
        ]
    elif any(kw in text_lower for kw in ["write", "draft", "document"]):
        subtasks = [
            {"title": f"Outline: {title}", "description": "Create structure and outline"},
            {"title": f"Draft: {title}", "description": "Write initial content"},
            {"title": f"Edit & Polish: {title}", "description": "Refine and finalize"},
        ]
    else:
        # Generic decomposition
        subtasks = [
            {"title": f"Setup: {title}", "description": "Prepare resources and context"},
            {"title": f"Execute: {title}", "description": "Carry out the main work"},
            {"title": f"Finalize: {title}", "description": "Review and deliver outputs"},
        ]

    return subtasks


def _build_initial_prompt(task: dict, agent: dict) -> str:
    """Build the initial prompt to send to the agent session."""
    soul = agent.get("soul_config") or {}
    if isinstance(soul, str):
        try:
            soul = json.loads(soul)
        except Exception:
            soul = {}

    title = task.get("title", "")
    description = task.get("description", "") or ""
    priority = task.get("priority", "medium")
    tags = task.get("tags", [])

    prompt = f"""## Task Assignment

**Task**: {title}
**Priority**: {priority.upper()}
{f'**Tags**: {", ".join(tags)}' if tags else ''}
{f'**Details**: {description}' if description else ''}

---

Please begin working on this task. Structure your response with:
1. **Understanding** — Confirm you understand the task
2. **Approach** — Your planned approach (3-5 steps)
3. **Execution** — Begin executing step 1

Report your progress clearly. If you need clarification or additional resources, ask specifically.
"""
    return prompt


async def _persist_message(task_id: str, session_id: str | None, role: str,
                            content: str, agent: dict | None = None) -> dict:
    """Save a message to task_messages and broadcast SSE."""
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
    Main dispatch entry point. Called by the orchestrator router.
    - Validates task exists and not already dispatched
    - Decomposes if warranted
    - Creates/selects agent via Agent Factory
    - Creates gateway session
    - Sends initial prompt
    - Runs async response loop
    Returns status dict.
    """
    db = await get_db()

    # Load task
    async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise ValueError(f"Task {task_id} not found")

    task = dict(row)
    task["tags"] = json.loads(task.get("tags", "[]"))

    # Guard: already dispatched
    if task.get("gateway_session_id"):
        return {"ok": True, "message": "Task already dispatched", "task_id": task_id}

    # Guard: already being dispatched
    if task_id in _active_dispatches:
        return {"ok": True, "message": "Dispatch already in progress", "task_id": task_id}

    # Update status to assigned
    await db.execute(
        "UPDATE tasks SET status = 'assigned', updated_at = datetime('now') WHERE id = ?",
        (task_id,),
    )
    await db.commit()
    await sse.broadcast("task.updated", {**task, "status": "assigned"})

    # Decompose task (create subtasks)
    subtasks = _decompose_task(task)
    if subtasks:
        for st in subtasks:
            sub_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO tasks (id, title, description, parent_task_id, priority, tags, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'inbox')""",
                (sub_id, st["title"], st["description"], task_id, task["priority"], task.get("tags", "[]") if isinstance(task.get("tags"), str) else json.dumps(task.get("tags", []))),
            )
        await db.commit()
        await sse.broadcast("task.subtasks_created", {"task_id": task_id, "count": len(subtasks)})
        logger.info(f"Orchestrator: decomposed task {task_id} into {len(subtasks)} subtasks")

    # Persist orchestrator kickoff message
    await _persist_message(
        task_id, None, "orchestrator",
        f"🚀 Task dispatched. Creating specialist agent...\n{'Decomposed into ' + str(len(subtasks)) + ' subtasks.' if subtasks else ''}",
    )

    # Create agent via Agent Factory
    agent = await create_agent_for_task(task)

    # Update task: assigned_agent_id
    await db.execute(
        "UPDATE tasks SET assigned_agent_id = ?, updated_at = datetime('now') WHERE id = ?",
        (agent["id"], task_id),
    )
    await db.commit()

    # Create gateway session
    session_id: str | None = None
    gw_session_id: str | None = None

    if gateway.connected:
        try:
            gw_agent_id = agent.get("gateway_agent_id")
            session_result = await gateway.create_session(
                agent_id=gw_agent_id,
                task_id=task_id,
            )
            gw_session_id = (
                session_result.get("id")
                or session_result.get("sessionId")
                or session_result.get("session_id")
            )
            logger.info(f"Orchestrator: created gateway session {gw_session_id}")
        except Exception as e:
            logger.warning(f"Orchestrator: failed to create gateway session (non-fatal): {e}")

    # Store session reference on task
    await db.execute(
        "UPDATE tasks SET gateway_session_id = ?, status = 'in_progress', updated_at = datetime('now') WHERE id = ?",
        (gw_session_id, task_id),
    )
    await db.commit()
    await sse.broadcast("task.updated", {**task, "status": "in_progress", "assigned_agent_id": agent["id"]})

    # Build and send initial prompt
    initial_prompt = _build_initial_prompt(task, agent)

    # Persist user message
    await _persist_message(task_id, gw_session_id, "orchestrator", initial_prompt)

    # If gateway connected, send to gateway session
    if gateway.connected and gw_session_id:
        dispatch_task = asyncio.create_task(
            _run_gateway_session(task_id, gw_session_id, initial_prompt, agent)
        )
        _active_dispatches[task_id] = dispatch_task
    else:
        # Offline mode: simulate agent thinking
        sim_task = asyncio.create_task(
            _simulate_agent_response(task_id, gw_session_id, agent)
        )
        _active_dispatches[task_id] = sim_task

    return {
        "ok": True,
        "message": f"Task dispatched to agent {agent['name']}",
        "task_id": task_id,
        "agent_id": agent["id"],
        "agent_name": agent["name"],
        "session_id": gw_session_id,
        "subtasks_created": len(subtasks),
    }


async def _run_gateway_session(task_id: str, session_id: str, prompt: str, agent: dict):
    """Send message to gateway and wait for responses via events."""
    try:
        await gateway.send_message(session_id, prompt)
        logger.info(f"Orchestrator: sent initial prompt to session {session_id}")
    except Exception as e:
        logger.error(f"Orchestrator: failed to send message: {e}")
        await _persist_message(
            task_id, session_id, "orchestrator",
            f"⚠️ Failed to send to gateway: {e}"
        )
    finally:
        _active_dispatches.pop(task_id, None)


async def _simulate_agent_response(task_id: str, session_id: str | None, agent: dict):
    """
    Offline simulation: produce realistic-looking agent responses.
    Used when gateway is not connected, for UI development/demo.
    """
    await asyncio.sleep(1.5)

    name = agent.get("name", "Agent")
    role = agent.get("role", "researcher")
    soul = agent.get("soul_config") or {}
    if isinstance(soul, str):
        try:
            soul = json.loads(soul)
        except Exception:
            soul = {}

    steps = [
        f"✅ **Understanding confirmed.** I'm {name}, your {role} specialist.\n\nI've analyzed the task and have a clear picture of what's needed.",
        f"📋 **Approach planned:**\n1. {soul.get('skills', ['gather information'])[0].replace('_', ' ').title()}\n2. Deep analysis of available data\n3. Synthesis and structured output\n4. Quality review\n5. Final deliverable\n\nStarting with step 1 now...",
        f"🔍 **Step 1 — Executing...**\n\nGathering relevant context and resources. This involves cross-referencing multiple knowledge areas related to the task.\n\nProgress: ████████░░ 80%",
        f"✨ **Initial findings:**\n\nKey insights identified:\n• Core requirement is well-scoped\n• Multiple viable approaches exist\n• Recommend prioritizing quality over speed\n\nMoving to synthesis phase...",
        f"📊 **Analysis complete.** Here's my structured output:\n\n**Summary**: Task has been processed successfully.\n**Confidence**: High\n**Recommended next steps**: Review outputs and proceed to implementation.\n\n*Task ready for review.*",
    ]

    for i, step in enumerate(steps):
        await asyncio.sleep(2 + i * 1.5)
        await _persist_message(task_id, session_id, "assistant", step, agent)

    # Mark task as review
    db = await get_db()
    await db.execute(
        "UPDATE tasks SET status = 'review', updated_at = datetime('now') WHERE id = ?",
        (task_id,),
    )
    await db.commit()
    await sse.broadcast("task.updated", {"id": task_id, "status": "review"})
    _active_dispatches.pop(task_id, None)
