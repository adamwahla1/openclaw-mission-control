"""Memory CRUD + AI extraction + graph endpoints."""

import json
import uuid
from fastapi import APIRouter, HTTPException, Query
from database import get_db
from models.memory import MemoryCreate, MemoryUpdate, ConnectionCreate, MemoryExtractRequest
from services.sse_broadcaster import sse

router = APIRouter(prefix="/api/memories", tags=["memories"])


# ── List memories ────────────────────────────────────────────────────────────
@router.get("")
async def list_memories(
    agent_id: str | None = None,
    memory_type: str | None = None,
    category: str | None = None,
    min_importance: float = 0.0,
    search: str | None = None,
    limit: int = Query(default=100, le=500),
):
    db = await get_db()
    conditions = ["importance >= ?"]
    params: list = [min_importance]

    if agent_id:
        conditions.append("agent_id = ?")
        params.append(agent_id)
    if memory_type:
        conditions.append("memory_type = ?")
        params.append(memory_type)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if search:
        conditions.append("content LIKE ?")
        params.append(f"%{search}%")

    where = " AND ".join(conditions)
    params.append(limit)

    async with db.execute(
        f"SELECT * FROM memories WHERE {where} ORDER BY importance DESC, created_at DESC LIMIT ?",
        params,
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── Create memory ────────────────────────────────────────────────────────────
@router.post("", status_code=201)
async def create_memory(body: MemoryCreate):
    db = await get_db()
    mem_id = str(uuid.uuid4())

    await db.execute(
        """INSERT INTO memories (id, content, memory_type, category, source, importance, tags, connections, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        (mem_id, body.content, body.memory_type, body.category, body.source,
         body.importance, json.dumps(body.tags), json.dumps(body.connections)),
    )
    await db.commit()

    async with db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)) as cursor:
        row = await cursor.fetchone()
    mem = dict(row)

    await sse.broadcast("memory.created", mem)
    return mem


# ── Stats (MUST be before /{memory_id}) ──────────────────────────────────────
@router.get("/stats")
async def memory_stats():
    db = await get_db()
    stats = {}

    async with db.execute("SELECT COUNT(*) as total FROM memories") as cursor:
        row = await cursor.fetchone()
        stats["total"] = dict(row)["total"] if row else 0

    async with db.execute("SELECT memory_type, COUNT(*) as cnt FROM memories GROUP BY memory_type") as cursor:
        rows = await cursor.fetchall()
        stats["by_type"] = {r["memory_type"]: dict(r)["cnt"] for r in rows}

    async with db.execute("SELECT category, COUNT(*) as cnt FROM memories GROUP BY category ORDER BY cnt DESC LIMIT 10") as cursor:
        rows = await cursor.fetchall()
        stats["by_category"] = {r["category"]: dict(r)["cnt"] for r in rows}

    async with db.execute("SELECT AVG(importance) as avg_importance, AVG(decay_score) as avg_decay FROM memories") as cursor:
        row = await cursor.fetchone()
        d = dict(row) if row else {}
        stats["avg_importance"] = round(d.get("avg_importance", 0) or 0, 3)
        stats["avg_decay"] = round(d.get("avg_decay", 1.0) or 1.0, 3)

    async with db.execute("SELECT COUNT(*) as total FROM memory_connections") as cursor:
        row = await cursor.fetchone()
        stats["connections"] = dict(row)["total"] if row else 0

    return stats


# ── Graph data (MUST be before /{memory_id}) ─────────────────────────────────
@router.get("/graph/data")
async def get_graph_data(
    min_importance: float = 0.0,
    agent_id: str | None = None,
):
    """Get memories and connections formatted for D3.js force graph."""
    db = await get_db()

    conditions = ["importance >= ?"]
    params: list = [min_importance]
    if agent_id:
        conditions.append("agent_id = ?")
        params.append(agent_id)

    where = " AND ".join(conditions)

    async with db.execute(
        f"SELECT id, agent_id, content, memory_type, category, importance, decay_score, tags, created_at FROM memories WHERE {where} ORDER BY importance DESC LIMIT 300",
        params,
    ) as cursor:
        mem_rows = await cursor.fetchall()

    node_ids = {r["id"] for r in mem_rows}
    nodes = []
    for r in mem_rows:
        row = dict(r)
        try:
            row["tags"] = json.loads(row.get("tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            row["tags"] = []
        nodes.append(row)

    if node_ids:
        placeholders = ",".join("?" for _ in node_ids)
        async with db.execute(
            f"""SELECT source_memory_id, target_memory_id, connection_type, strength
                FROM memory_connections
                WHERE source_memory_id IN ({placeholders}) AND target_memory_id IN ({placeholders})""",
            list(node_ids) + list(node_ids),
        ) as cursor:
            conn_rows = await cursor.fetchall()
        links = [dict(r) for r in conn_rows]
    else:
        links = []

    return {"nodes": nodes, "links": links}


# ── AI Extract memories (MUST be before /{memory_id}) ────────────────────────
@router.post("/extract", status_code=201)
async def extract_memories(body: MemoryExtractRequest):
    """Use AI to extract memories from text content."""
    from services.ai_client import generate_json

    prompt = (
        f"Extract key memories from the following {body.source_type}. "
        f"For each memory, provide:\n"
        f"- content: The core fact/insight/procedure (concise, 1-2 sentences)\n"
        f"- memory_type: One of 'fact', 'insight', 'procedure', 'experience', 'preference'\n"
        f"- category: A domain category (e.g., 'technical', 'business', 'behavior', 'domain')\n"
        f"- importance: 0.0-1.0 (how significant is this?)\n"
        f"- tags: Array of 1-3 relevant tags\n\n"
        f"Source text:\n{body.source_text[:6000]}\n\n"
        f"Return a JSON array of memories. Example:\n"
        f'[{{"content": "...", "memory_type": "fact", "category": "technical", "importance": 0.8, "tags": ["api", "performance"]}}]'
    )

    try:
        response = await generate_json(
            prompt=prompt,
            system="You are a knowledge extraction expert. Extract concise, distinct memories from text. Each memory should capture ONE key piece of information. Be specific, not vague.",
            max_tokens=2048,
            temperature=0.3,
        )

        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0] if "```" in text else text
        text = text.strip()

        memories_data = json.loads(text)
        if not isinstance(memories_data, list):
            memories_data = [memories_data]

    except (json.JSONDecodeError, Exception):
        memories_data = [{
            "content": body.source_text[:200],
            "memory_type": "experience",
            "category": "general",
            "importance": 0.5,
            "tags": [body.source_type],
        }]

    db = await get_db()
    created = []
    for mem_data in memories_data[:20]:
        mem_id = str(uuid.uuid4())
        tags = mem_data.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        await db.execute(
            """INSERT INTO memories (id, agent_id, content, memory_type, category, source, importance, tags, connections, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', datetime('now'), datetime('now'))""",
            (mem_id, body.agent_id, mem_data.get("content", ""),
             mem_data.get("memory_type", "fact"), mem_data.get("category", "general"),
             body.source_type, mem_data.get("importance", 0.5), json.dumps(tags)),
        )
        created.append(mem_id)

    await db.commit()

    if created:
        placeholders = ",".join("?" for _ in created)
        async with db.execute(
            f"SELECT * FROM memories WHERE id IN ({placeholders})", created
        ) as cursor:
            rows = await cursor.fetchall()
        result = [dict(r) for r in rows]
    else:
        result = []

    await sse.broadcast("memory.batch_created", {"count": len(result), "memories": result})
    return result


# ── Decay simulation (MUST be before /{memory_id}) ───────────────────────────
@router.post("/decay")
async def apply_decay():
    """Apply time-based decay to all memories."""
    db = await get_db()
    await db.execute("""
        UPDATE memories SET
            decay_score = CASE
                WHEN last_accessed IS NULL THEN decay_score * 0.9
                WHEN julianday('now') - julianday(last_accessed) < 1 THEN LEAST(1.0, decay_score * 1.05)
                WHEN julianday('now') - julianday(last_accessed) < 7 THEN decay_score * 0.98
                ELSE decay_score * 0.92
            END,
            updated_at = datetime('now')
        WHERE decay_score > 0.05
    """)
    await db.commit()

    async with db.execute("SELECT COUNT(*) as count FROM memories WHERE decay_score <= 0.05") as cursor:
        row = await cursor.fetchone()
    forgotten = row["count"] if row else 0

    await db.execute("DELETE FROM memory_connections WHERE source_memory_id IN (SELECT id FROM memories WHERE decay_score <= 0.02)")
    await db.execute("DELETE FROM memories WHERE decay_score <= 0.02")
    await db.commit()

    return {"status": "ok", "forgotten": forgotten}


# ── Get memory ───────────────────────────────────────────────────────────────
@router.get("/{memory_id}")
async def get_memory(memory_id: str):
    db = await get_db()
    async with db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Memory not found")
    mem = dict(row)

    async with db.execute(
        """SELECT mc.*, m.content AS target_content, m.memory_type AS target_type
           FROM memory_connections mc
           JOIN memories m ON m.id = mc.target_memory_id
           WHERE mc.source_memory_id = ?""",
        (memory_id,),
    ) as cursor:
        conns = await cursor.fetchall()
    mem["outgoing_connections"] = [dict(c) for c in conns]

    async with db.execute(
        """SELECT mc.*, m.content AS source_content, m.memory_type AS source_type
           FROM memory_connections mc
           JOIN memories m ON m.id = mc.source_memory_id
           WHERE mc.target_memory_id = ?""",
        (memory_id,),
    ) as cursor:
        incomings = await cursor.fetchall()
    mem["incoming_connections"] = [dict(c) for c in incomings]

    await db.execute(
        "UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id = ?",
        (memory_id,),
    )
    await db.commit()

    return mem


# ── Update memory ────────────────────────────────────────────────────────────
@router.patch("/{memory_id}")
async def update_memory(memory_id: str, body: MemoryUpdate):
    db = await get_db()
    async with db.execute("SELECT id FROM memories WHERE id = ?", (memory_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Memory not found")

    allowed = {"content", "memory_type", "category", "importance", "decay_score"}
    updates = []
    params = []
    for field, value in body.model_dump(exclude_none=True).items():
        if field in allowed:
            updates.append(f"{field} = ?")
            params.append(value)
        elif field == "tags":
            updates.append("tags = ?")
            params.append(json.dumps(value))

    if not updates:
        raise HTTPException(400, "No valid fields to update")

    updates.append("updated_at = datetime('now')")
    params.append(memory_id)
    await db.execute(f"UPDATE memories SET {', '.join(updates)} WHERE id = ?", params)
    await db.commit()

    async with db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)) as cursor:
        row = await cursor.fetchone()
    mem = dict(row)
    await sse.broadcast("memory.updated", mem)
    return mem


# ── Delete memory ────────────────────────────────────────────────────────────
@router.delete("/{memory_id}", status_code=204)
async def delete_memory(memory_id: str):
    db = await get_db()
    await db.execute("DELETE FROM memory_connections WHERE source_memory_id = ? OR target_memory_id = ?", (memory_id, memory_id))
    await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    await db.commit()
    await sse.broadcast("memory.deleted", {"id": memory_id})


# ── Create connection ────────────────────────────────────────────────────────
@router.post("/{memory_id}/connections", status_code=201)
async def create_connection(memory_id: str, body: ConnectionCreate):
    db = await get_db()
    async with db.execute("SELECT id FROM memories WHERE id = ?", (memory_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Source memory not found")
    async with db.execute("SELECT id FROM memories WHERE id = ?", (body.target_memory_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Target memory not found")

    conn_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO memory_connections (id, source_memory_id, target_memory_id, connection_type, strength)
           VALUES (?, ?, ?, ?, ?)""",
        (conn_id, memory_id, body.target_memory_id, body.connection_type, body.strength),
    )
    await db.commit()

    async with db.execute("SELECT * FROM memory_connections WHERE id = ?", (conn_id,)) as cursor:
        row = await cursor.fetchone()
    return dict(row)


# ── Delete connection ────────────────────────────────────────────────────────
@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(connection_id: str):
    db = await get_db()
    await db.execute("DELETE FROM memory_connections WHERE id = ?", (connection_id,))
    await db.commit()
