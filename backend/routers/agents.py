"""Agent management endpoints — synced with OpenClaw Gateway."""
import json
import uuid
from fastapi import APIRouter, HTTPException
from database import get_db
from models.agent import AgentCreate, AgentUpdate
from services.gateway_bridge import gateway
from services.sse_broadcaster import sse

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents():
    db = await get_db()
    async with db.execute("SELECT * FROM agents ORDER BY created_at DESC") as cursor:
        rows = await cursor.fetchall()
    return [_row_to_agent(r) for r in rows]


@router.get("/gateway")
async def list_gateway_agents():
    """Fetch agents directly from OpenClaw Gateway."""
    if not gateway.connected:
        raise HTTPException(503, "Gateway not connected")
    return await gateway.list_agents()


@router.post("/sync")
async def sync_agents():
    """Sync agents from OpenClaw Gateway to local DB."""
    if not gateway.connected:
        raise HTTPException(503, "Gateway not connected")

    gw_agents = await gateway.list_agents()
    db = await get_db()
    synced = 0

    for ga in gw_agents:
        gw_id = ga.get("id") or ga.get("agentId", "")
        name = ga.get("name", "Unknown")
        role = ga.get("role", "")

        # Check if already tracked
        async with db.execute(
            "SELECT id FROM agents WHERE gateway_agent_id = ?", (gw_id,)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            await db.execute(
                "UPDATE agents SET name = ?, role = ?, status = 'active', updated_at = datetime('now') WHERE gateway_agent_id = ?",
                (name, role, gw_id),
            )
        else:
            await db.execute(
                "INSERT INTO agents (id, gateway_agent_id, name, role, status) VALUES (?, ?, ?, ?, 'active')",
                (str(uuid.uuid4()), gw_id, name, role),
            )
        synced += 1

    await db.commit()
    await sse.broadcast("agents.synced", {"count": synced})
    return {"synced": synced}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    db = await get_db()
    async with db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Agent not found")
    return _row_to_agent(row)


@router.post("", status_code=201)
async def create_agent(body: AgentCreate):
    db = await get_db()
    agent_id = str(uuid.uuid4())
    soul_json = json.dumps(body.soul_config)

    # If gateway connected, also create on OpenClaw
    gw_agent_id = body.gateway_agent_id
    if gateway.connected and not gw_agent_id:
        try:
            result = await gateway.create_agent(body.name, body.role, body.soul_config)
            gw_agent_id = result.get("id") or result.get("agentId")
        except Exception as e:
            # Non-fatal — create locally even if gateway fails
            pass

    await db.execute(
        """INSERT INTO agents (id, gateway_agent_id, name, role, soul_config)
           VALUES (?, ?, ?, ?, ?)""",
        (agent_id, gw_agent_id, body.name, body.role, soul_json),
    )
    await db.commit()

    agent = await get_agent(agent_id)
    await sse.broadcast("agent.created", agent)
    return agent


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdate):
    db = await get_db()
    async with db.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Agent not found")

    updates = []
    params = []
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "soul_config":
            updates.append("soul_config = ?")
            params.append(json.dumps(value))
        else:
            updates.append(f"{field} = ?")
            params.append(value)

    if updates:
        updates.append("updated_at = datetime('now')")
        params.append(agent_id)
        await db.execute(f"UPDATE agents SET {', '.join(updates)} WHERE id = ?", params)
        await db.commit()

    agent = await get_agent(agent_id)
    await sse.broadcast("agent.updated", agent)
    return agent


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    db = await get_db()
    async with db.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Agent not found")
    await db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    await db.commit()
    await sse.broadcast("agent.deleted", {"id": agent_id})
    return {"ok": True}


def _row_to_agent(row) -> dict:
    d = dict(row)
    try:
        d["soul_config"] = json.loads(d.get("soul_config", "{}"))
    except (json.JSONDecodeError, TypeError):
        d["soul_config"] = {}
    return d
