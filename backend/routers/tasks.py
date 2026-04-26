"""Task CRUD endpoints."""
import json
import uuid
from fastapi import APIRouter, HTTPException
from database import get_db
from models.task import TaskCreate, TaskUpdate, Task
from services.sse_broadcaster import sse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

VALID_STATUSES = ["inbox", "assigned", "in_progress", "review", "quality_review", "done", "archived"]
VALID_PRIORITIES = ["critical", "high", "medium", "low"]


@router.get("")
async def list_tasks(status: str | None = None, project_id: str | None = None):
    db = await get_db()
    query = "SELECT * FROM tasks WHERE is_template = 0"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if project_id:
        query += " AND id IN (SELECT task_id FROM project_tasks WHERE project_id = ?)"
        params.append(project_id)
    query += " ORDER BY created_at DESC"
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    return [_row_to_task(r) for r in rows]


@router.get("/{task_id}")
async def get_task(task_id: str):
    db = await get_db()
    async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    return _row_to_task(row)


@router.post("", status_code=201)
async def create_task(body: TaskCreate):
    db = await get_db()
    task_id = str(uuid.uuid4())
    tags_json = json.dumps(body.tags)
    await db.execute(
        """INSERT INTO tasks (id, title, description, priority, board_id, project_id,
           assigned_agent_id, parent_task_id, tags)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, body.title, body.description, body.priority, body.board_id,
         body.project_id, body.assigned_agent_id, body.parent_task_id, tags_json),
    )
    await db.commit()

    # Log activity
    await db.execute(
        "INSERT INTO activities (id, event_type, target_type, target_id, details) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), "task.created", "task", task_id, json.dumps({"title": body.title})),
    )
    await db.commit()

    task = await get_task(task_id)
    await sse.broadcast("task.created", task)
    return task


@router.patch("/{task_id}")
async def update_task(task_id: str, body: TaskUpdate):
    db = await get_db()
    # Verify exists
    async with db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Task not found")

    updates = []
    params = []
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "tags":
            updates.append("tags = ?")
            params.append(json.dumps(value))
        else:
            updates.append(f"{field} = ?")
            params.append(value)

    if not updates:
        raise HTTPException(400, "No fields to update")

    updates.append("updated_at = datetime('now')")
    params.append(task_id)

    await db.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    await db.commit()

    task = await get_task(task_id)
    await sse.broadcast("task.updated", task)
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    db = await get_db()
    async with db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Task not found")
    await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await db.commit()
    await sse.broadcast("task.deleted", {"id": task_id})
    return {"ok": True}


@router.get("/{task_id}/messages")
async def get_task_messages(task_id: str):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM task_messages WHERE task_id = ? ORDER BY created_at ASC", (task_id,)
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("/{task_id}/comments")
async def add_comment(task_id: str, content: str, author_type: str = "user"):
    db = await get_db()
    comment_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO task_comments (id, task_id, author_type, content) VALUES (?, ?, ?, ?)",
        (comment_id, task_id, author_type, content),
    )
    await db.commit()
    return {"id": comment_id, "task_id": task_id, "content": content}


def _row_to_task(row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d.get("tags", "[]"))
    d["is_template"] = bool(d.get("is_template", 0))
    return d
