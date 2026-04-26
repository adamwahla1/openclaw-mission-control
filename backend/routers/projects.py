"""Project CRUD endpoints with auto-bundle support."""
import json
import uuid
from collections import defaultdict
from fastapi import APIRouter, HTTPException
from database import get_db
from models.project import ProjectCreate, ProjectUpdate, ProjectFileCreate, HandoverCreate
from services.sse_broadcaster import sse

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ── List ──────────────────────────────────────────────────────────────────────
@router.get("")
async def list_projects():
    db = await get_db()
    async with db.execute(
        """SELECT p.*, COUNT(pt.task_id) AS task_count
           FROM projects p
           LEFT JOIN project_tasks pt ON pt.project_id = p.id
           GROUP BY p.id
           ORDER BY p.created_at DESC"""
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── Create ────────────────────────────────────────────────────────────────────
@router.post("", status_code=201)
async def create_project(body: ProjectCreate):
    db = await get_db()
    project_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO projects (id, name, description)
           VALUES (?, ?, ?)""",
        (project_id, body.name, body.description),
    )
    await db.commit()
    project = await _get_project(project_id)
    await sse.broadcast("project.created", project)
    return project


# ── Get ───────────────────────────────────────────────────────────────────────
@router.get("/{project_id}")
async def get_project(project_id: str):
    return await _get_project(project_id)


# ── Update ────────────────────────────────────────────────────────────────────
@router.patch("/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate):
    db = await get_db()
    async with db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Project not found")

    updates = []
    params = []
    for field, value in body.model_dump(exclude_unset=True).items():
        updates.append(f"{field} = ?")
        params.append(value)

    if not updates:
        raise HTTPException(400, "No fields to update")

    updates.append("updated_at = datetime('now')")
    params.append(project_id)
    await db.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", params)
    await db.commit()

    project = await _get_project(project_id)
    await sse.broadcast("project.updated", project)
    return project


# ── Delete ────────────────────────────────────────────────────────────────────
@router.delete("/{project_id}")
async def delete_project(project_id: str):
    db = await get_db()
    async with db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Project not found")
    await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    await db.commit()
    await sse.broadcast("project.deleted", {"id": project_id})
    return {"ok": True}


# ── Task associations ─────────────────────────────────────────────────────────
@router.post("/{project_id}/tasks", status_code=201)
async def add_task_to_project(project_id: str, body: dict):
    task_id = body.get("task_id")
    if not task_id:
        raise HTTPException(400, "task_id required")

    db = await get_db()
    async with db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Project not found")
    async with db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Task not found")

    # Idempotent — ignore if already linked (composite PK)
    await db.execute(
        "INSERT OR IGNORE INTO project_tasks (project_id, task_id) VALUES (?, ?)",
        (project_id, task_id),
    )
    await db.commit()
    return {"ok": True, "project_id": project_id, "task_id": task_id}


@router.delete("/{project_id}/tasks/{task_id}")
async def remove_task_from_project(project_id: str, task_id: str):
    db = await get_db()
    await db.execute(
        "DELETE FROM project_tasks WHERE project_id = ? AND task_id = ?",
        (project_id, task_id),
    )
    await db.commit()
    return {"ok": True}


# ── Files ─────────────────────────────────────────────────────────────────────
@router.get("/{project_id}/files")
async def list_project_files(project_id: str):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM project_files WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("/{project_id}/files", status_code=201)
async def add_project_file(project_id: str, body: ProjectFileCreate):
    db = await get_db()
    async with db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Project not found")

    file_id = str(uuid.uuid4())
    pinned = 1 if body.pinned else 0
    await db.execute(
        """INSERT INTO project_files (id, project_id, task_id, filename, filepath, file_type, pinned)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (file_id, project_id, body.task_id, body.filename, body.filepath, body.file_type or "", pinned),
    )
    await db.commit()

    async with db.execute("SELECT * FROM project_files WHERE id = ?", (file_id,)) as cursor:
        row = await cursor.fetchone()
    file_dict = dict(row)
    await sse.broadcast("project.file_added", {"project_id": project_id, "file": file_dict})
    return file_dict


# ── Handovers ─────────────────────────────────────────────────────────────────
@router.get("/{project_id}/handovers")
async def list_project_handovers(project_id: str):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM project_handovers WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [_row_to_handover(r) for r in rows]


@router.post("/{project_id}/handovers", status_code=201)
async def create_project_handover(project_id: str, body: HandoverCreate):
    db = await get_db()
    async with db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Project not found")

    handover_id = str(uuid.uuid4())
    key_decisions_json = json.dumps(body.key_decisions or [])
    open_questions_json = json.dumps(body.open_questions or [])
    await db.execute(
        """INSERT INTO project_handovers (id, project_id, task_id, content_md, summary, key_decisions, open_questions)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (handover_id, project_id, body.task_id, body.content_md, body.summary or "", key_decisions_json, open_questions_json),
    )
    await db.commit()

    async with db.execute("SELECT * FROM project_handovers WHERE id = ?", (handover_id,)) as cursor:
        row = await cursor.fetchone()
    handover_dict = _row_to_handover(row)
    await sse.broadcast("project.handover_created", {"project_id": project_id, "handover": handover_dict})
    return handover_dict


# ── Auto-bundle ───────────────────────────────────────────────────────────────
@router.post("/auto-bundle")
async def auto_bundle():
    """Auto-bundle unassigned tasks into projects by tag clustering and keyword similarity."""
    db = await get_db()

    # 1. Get all tasks without a project
    async with db.execute(
        """SELECT * FROM tasks
           WHERE id NOT IN (SELECT task_id FROM project_tasks)
           AND is_template = 0"""
    ) as cursor:
        unassigned = await cursor.fetchall()

    if not unassigned:
        return {"created": 0, "projects": []}

    # Parse tags for each task
    tasks_parsed = []
    for row in unassigned:
        d = dict(row)
        try:
            d["tags"] = json.loads(d.get("tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
        tasks_parsed.append(d)

    # 2. Cluster by tag overlap (tasks sharing 2+ tags)
    tag_clusters = _cluster_by_tags(tasks_parsed)

    # 3. Further merge clusters by keyword similarity in title
    tag_clusters = _merge_by_keyword_similarity(tag_clusters)

    # 4. Create a project per cluster
    created_projects = []
    for cluster in tag_clusters:
        if len(cluster) < 1:
            continue

        # Derive name from common tags
        common_tags = _find_common_tags(cluster)
        if common_tags:
            name = " / ".join(common_tags[:3]).title()
        else:
            name = f"Auto-bundled Project {len(created_projects) + 1}"

        project_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO projects (id, name, description, status, auto_detected, detection_method)
               VALUES (?, ?, ?, 'active', 1, 'tag_clustering')""",
            (project_id, name, f"Auto-bundled from {len(cluster)} unassigned tasks"),
        )

        # Assign tasks to project
        for task in cluster:
            await db.execute(
                "INSERT INTO project_tasks (project_id, task_id) VALUES (?, ?)",
                (project_id, task["id"]),
            )

        created_projects.append({"id": project_id, "name": name, "task_count": len(cluster)})

    await db.commit()

    # Broadcast events for each created project
    for proj in created_projects:
        project = await _get_project(proj["id"])
        await sse.broadcast("project.created", project)

    return {"created": len(created_projects), "projects": created_projects}


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _get_project(project_id: str) -> dict:
    db = await get_db()
    async with db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Project not found")
    project = dict(row)

    # Tasks
    async with db.execute(
        """SELECT t.* FROM tasks t
           JOIN project_tasks pt ON pt.task_id = t.id
           WHERE pt.project_id = ?""",
        (project_id,),
    ) as cursor:
        task_rows = await cursor.fetchall()
    project["tasks"] = [_row_to_task(r) for r in task_rows]

    # Files
    async with db.execute(
        "SELECT * FROM project_files WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ) as cursor:
        file_rows = await cursor.fetchall()
    project["files"] = [dict(r) for r in file_rows]

    # Handovers
    async with db.execute(
        "SELECT * FROM project_handovers WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ) as cursor:
        handover_rows = await cursor.fetchall()
    project["handovers"] = [_row_to_handover(r) for r in handover_rows]

    return project


def _row_to_task(row) -> dict:
    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["tags"] = []
    d["is_template"] = bool(d.get("is_template", 0))
    return d


def _row_to_handover(row) -> dict:
    d = dict(row)
    for field in ("key_decisions", "open_questions"):
        try:
            d[field] = json.loads(d.get(field, "[]"))
        except (json.JSONDecodeError, TypeError):
            d[field] = []
    return d


def _cluster_by_tags(tasks: list[dict]) -> list[list[dict]]:
    """Group tasks that share 2+ tags into clusters using union-find."""
    parent = {t["id"]: t["id"] for t in tasks}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Compare all pairs
    for i, t1 in enumerate(tasks):
        for t2 in tasks[i + 1:]:
            shared = set(t1["tags"]) & set(t2["tags"])
            if len(shared) >= 2:
                union(t1["id"], t2["id"])

    # Collect clusters
    clusters: dict[str, list[dict]] = defaultdict(list)
    for t in tasks:
        clusters[find(t["id"])].append(t)

    return list(clusters.values())


def _merge_by_keyword_similarity(clusters: list[list[dict]]) -> list[list[dict]]:
    """Merge clusters whose tasks share a common word >4 chars in their titles."""
    # Extract significant words from each cluster
    def cluster_words(cluster: list[dict]) -> set[str]:
        words = set()
        for task in cluster:
            for w in (task.get("title") or "").split():
                if len(w) > 4:
                    words.add(w.lower())
        return words

    # Union-find on clusters
    parent = {i: i for i in range(len(clusters))}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(clusters)):
        for j in range(i + 1, len(clusters)):
            w_i = cluster_words(clusters[i])
            w_j = cluster_words(clusters[j])
            if w_i & w_j:
                union(i, j)

    merged: dict[int, list[dict]] = defaultdict(list)
    for i, cluster in enumerate(clusters):
        merged[find(i)].extend(cluster)

    return list(merged.values())


def _find_common_tags(cluster: list[dict]) -> list[str]:
    """Find tags shared by all tasks in a cluster."""
    if not cluster:
        return []
    common = set(cluster[0]["tags"])
    for task in cluster[1:]:
        common &= set(task["tags"])
    return sorted(common)
