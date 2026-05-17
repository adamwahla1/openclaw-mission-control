"""Agent management endpoints backed by Mission Control native state."""
import json
import uuid
from fastapi import APIRouter, HTTPException
from database import get_db
from models.agent import AgentCreate, AgentUpdate
from services.runtime_registry import runtime_registry
from services.sse_broadcaster import sse

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents():
    db = await get_db()
    return await runtime_registry.native.list_agents(db)


@router.get("/gateway")
async def list_gateway_agents():
    """Fetch agents from OpenClaw only when the optional adapter is active."""
    db = await get_db()
    status = await runtime_registry.status(db)
    if status["active_runtime"] != "openclaw":
        return []
    try:
        from services.gateway_bridge import gateway

        if not gateway.connected:
            raise HTTPException(503, "OpenClaw runtime is not connected")
        return await gateway.list_agents()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, str(exc))


@router.post("/sync")
async def sync_agents():
    """Sync agents from OpenClaw when the optional adapter is active."""
    db = await get_db()
    status = await runtime_registry.status(db)
    if status["active_runtime"] != "openclaw":
        return {"synced": 0, "message": "Native runtime is active; OpenClaw sync skipped."}

    from services.gateway_bridge import gateway

    if not gateway.connected:
        raise HTTPException(503, "OpenClaw runtime is not connected")

    gw_agents = await gateway.list_agents()
    synced = 0

    for ga in gw_agents:
        gw_id = ga.get("id") or ga.get("agentId", "")
        name = ga.get("name", "Unknown")
        role = ga.get("role", "")

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
    try:
        return await runtime_registry.native.get_agent(db, agent_id)
    except ValueError:
        raise HTTPException(404, "Agent not found")


@router.post("", status_code=201)
async def create_agent(body: AgentCreate):
    db = await get_db()
    return await runtime_registry.native.create_agent(
        db,
        name=body.name,
        role=body.role,
        soul_config=body.soul_config,
    )


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
