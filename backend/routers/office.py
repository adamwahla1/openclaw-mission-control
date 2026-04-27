"""Virtual Office CRUD + position/event management."""

import json
import uuid
from fastapi import APIRouter, HTTPException
from database import get_db
from services.sse_broadcaster import sse

router = APIRouter(prefix="/api/office", tags=["office"])


# ── Rooms ────────────────────────────────────────────────────────────────────

@router.get("/rooms")
async def list_rooms():
    db = await get_db()
    async with db.execute("SELECT * FROM office_rooms ORDER BY y, x") as cursor:
        rows = await cursor.fetchall()
    rooms = [dict(r) for r in rows]

    # Add agent positions for each room
    for room in rooms:
        async with db.execute(
            """SELECT op.*, a.name, a.role, a.status AS agent_status
               FROM office_positions op
               JOIN agents a ON a.id = op.agent_id
               WHERE op.room_id = ?""",
            (room["id"],),
        ) as cursor:
            agents = await cursor.fetchall()
        room["agents"] = [dict(a) for a in agents]

    return rooms


@router.post("/rooms", status_code=201)
async def create_room(body: dict):
    db = await get_db()
    room_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO office_rooms (id, name, room_type, x, y, width, height, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (room_id, body.get("name", "New Room"), body.get("room_type", "desk"),
         body.get("x", 0), body.get("y", 0), body.get("width", 120),
         body.get("height", 80), json.dumps(body.get("metadata", {}))),
    )
    await db.commit()

    async with db.execute("SELECT * FROM office_rooms WHERE id = ?", (room_id,)) as cursor:
        row = await cursor.fetchone()
    room = dict(row)
    await sse.broadcast("office.room_created", room)
    return room


@router.patch("/rooms/{room_id}")
async def update_room(room_id: str, body: dict):
    db = await get_db()
    async with db.execute("SELECT id FROM office_rooms WHERE id = ?", (room_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Room not found")

    allowed = {"name", "room_type", "x", "y", "width", "height"}
    updates = []
    params = []
    for field, value in body.items():
        if field in allowed:
            updates.append(f"{field} = ?")
            params.append(value)
        elif field == "metadata":
            updates.append("metadata = ?")
            params.append(json.dumps(value))

    if not updates:
        raise HTTPException(400, "No valid fields")

    params.append(room_id)
    await db.execute(f"UPDATE office_rooms SET {', '.join(updates)} WHERE id = ?", params)
    await db.commit()

    async with db.execute("SELECT * FROM office_rooms WHERE id = ?", (room_id,)) as cursor:
        row = await cursor.fetchone()
    return dict(row)


@router.delete("/rooms/{room_id}", status_code=204)
async def delete_room(room_id: str):
    db = await get_db()
    await db.execute("UPDATE office_positions SET room_id = NULL WHERE room_id = ?", (room_id,))
    await db.execute("DELETE FROM office_rooms WHERE id = ?", (room_id,))
    await db.commit()


# ── Agent positions ──────────────────────────────────────────────────────────

@router.get("/positions")
async def list_positions():
    db = await get_db()
    async with db.execute(
        """SELECT op.*, a.name, a.role, a.status AS agent_status
           FROM office_positions op
           JOIN agents a ON a.id = op.agent_id"""
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("/positions/{agent_id}", status_code=201)
async def set_position(agent_id: str, body: dict):
    """Set or update an agent's position in the office."""
    db = await get_db()
    async with db.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(404, "Agent not found")

    # Upsert position
    async with db.execute("SELECT id FROM office_positions WHERE agent_id = ?", (agent_id,)) as cursor:
        existing = await cursor.fetchone()

    if existing:
        allowed = {"room_id", "x", "y", "state", "facing"}
        updates = []
        params = []
        for field, value in body.items():
            if field in allowed:
                updates.append(f"{field} = ?")
                params.append(value)
        updates.append("updated_at = datetime('now')")
        params.append(agent_id)
        await db.execute(f"UPDATE office_positions SET {', '.join(updates)} WHERE agent_id = ?", params)
    else:
        pos_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO office_positions (id, agent_id, room_id, x, y, state, facing, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pos_id, agent_id, body.get("room_id"), body.get("x", 0),
             body.get("y", 0), body.get("state", "idle"), body.get("facing", "down"),
             json.dumps(body.get("metadata", {}))),
        )

    await db.commit()

    async with db.execute(
        """SELECT op.*, a.name, a.role, a.status AS agent_status
           FROM office_positions op
           JOIN agents a ON a.id = op.agent_id
           WHERE op.agent_id = ?""",
        (agent_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if row:
        await sse.broadcast("office.position_updated", dict(row))
        return dict(row)
    return {}


# ── Events ───────────────────────────────────────────────────────────────────

@router.get("/events")
async def list_events(limit: int = 50):
    db = await get_db()
    async with db.execute(
        """SELECT oe.*, a.name AS agent_name
           FROM office_events oe
           LEFT JOIN agents a ON a.id = oe.agent_id
           ORDER BY oe.created_at DESC LIMIT ?""",
        (limit,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("/events", status_code=201)
async def create_event(body: dict):
    db = await get_db()
    event_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO office_events (id, agent_id, room_id, event_type, data)
           VALUES (?, ?, ?, ?, ?)""",
        (event_id, body.get("agent_id"), body.get("room_id"),
         body.get("event_type", "movement"), json.dumps(body.get("data", {}))),
    )
    await db.commit()

    async with db.execute(
        """SELECT oe.*, a.name AS agent_name
           FROM office_events oe
           LEFT JOIN agents a ON a.id = oe.agent_id
           WHERE oe.id = ?""",
        (event_id,),
    ) as cursor:
        row = await cursor.fetchone()
    event = dict(row) if row else {}
    await sse.broadcast("office.event", event)
    return event


# ── Initialize default office layout ─────────────────────────────────────────

@router.post("/initialize", status_code=201)
async def initialize_office():
    """Create a default office layout with rooms."""
    db = await get_db()
    async with db.execute("SELECT COUNT(*) as count FROM office_rooms") as cursor:
        row = await cursor.fetchone()
        if row["count"] > 0:
            return {"status": "already_initialized", "rooms": row["count"]}

    default_rooms = [
        {"name": "Command Center", "room_type": "control", "x": 0, "y": 0, "width": 200, "height": 140},
        {"name": "Research Lab", "room_type": "desk", "x": 220, "y": 0, "width": 160, "height": 120},
        {"name": "War Room", "room_type": "meeting", "x": 0, "y": 160, "width": 180, "height": 130},
        {"name": "Innovation Hub", "room_type": "creative", "x": 200, "y": 140, "width": 180, "height": 150},
        {"name": "Quiet Zone", "room_type": "focus", "x": 400, "y": 0, "width": 120, "height": 120},
        {"name": "Lounge", "room_type": "social", "x": 400, "y": 140, "width": 120, "height": 130},
    ]

    created = []
    for room_data in default_rooms:
        room_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO office_rooms (id, name, room_type, x, y, width, height, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, '{}')""",
            (room_id, room_data["name"], room_data["room_type"],
             room_data["x"], room_data["y"], room_data["width"], room_data["height"]),
        )
        created.append(room_data["name"])

    # Place existing agents in rooms
    async with db.execute("SELECT id FROM agents") as cursor:
        agents = await cursor.fetchall()

    if agents:
        room_list = default_rooms
        for i, agent in enumerate(agents):
            room = room_list[i % len(room_list)]
            # Get room id
            async with db.execute(
                "SELECT id FROM office_rooms WHERE name = ?", (room["name"],)
            ) as cursor:
                room_row = await cursor.fetchone()
            if room_row:
                pos_id = str(uuid.uuid4())
                await db.execute(
                    """INSERT INTO office_positions (id, agent_id, room_id, x, y, state, facing, metadata)
                       VALUES (?, ?, ?, ?, ?, 'idle', 'down', '{}')""",
                    (pos_id, agent["id"], room_row["id"],
                     room["width"] // 2, room["height"] // 2),
                )

    await db.commit()
    return {"status": "initialized", "rooms": created}


# ── Simulate office activity ─────────────────────────────────────────────────

@router.post("/simulate")
async def simulate_office():
    """Simulate agents moving around and working in the office."""
    db = await get_db()

    async with db.execute(
        """SELECT op.*, a.name, a.role, a.status AS agent_status
           FROM office_positions op
           JOIN agents a ON a.id = op.agent_id"""
    ) as cursor:
        positions = await cursor.fetchall()

    if not positions:
        raise HTTPException(400, "No agents positioned in the office. Initialize first.")

    async with db.execute("SELECT * FROM office_rooms") as cursor:
        rooms = await cursor.fetchall()

    room_list = [dict(r) for r in rooms]
    events = []

    for pos in positions:
        pos_data = dict(pos)
        agent_name = pos_data.get("name", "Agent")
        old_state = pos_data.get("state", "idle")

        # Random state transitions based on agent status
        states = ["idle", "working", "thinking", "collaborating", "reviewing"]
        import random
        new_state = random.choice(states)

        # Move within room bounds
        room = None
        if pos_data.get("room_id"):
            for r in room_list:
                if r["id"] == pos_data["room_id"]:
                    room = r
                    break

        new_x = pos_data.get("x", 0)
        new_y = pos_data.get("y", 0)
        if room:
            new_x = min(room["width"] - 20, max(20, new_x + random.randint(-30, 30)))
            new_y = min(room["height"] - 20, max(20, new_y + random.randint(-30, 30)))

        # Update position
        await db.execute(
            "UPDATE office_positions SET state = ?, x = ?, y = ?, updated_at = datetime('now') WHERE agent_id = ?",
            (new_state, new_x, new_y, pos_data["agent_id"]),
        )

        # Create event
        event_id = str(uuid.uuid4())
        event_type = "state_change" if new_state != old_state else "movement"
        event_data = {
            "from_state": old_state,
            "to_state": new_state,
            "from_pos": {"x": pos_data.get("x", 0), "y": pos_data.get("y", 0)},
            "to_pos": {"x": new_x, "y": new_y},
        }
        await db.execute(
            """INSERT INTO office_events (id, agent_id, room_id, event_type, data)
               VALUES (?, ?, ?, ?, ?)""",
            (event_id, pos_data["agent_id"], pos_data.get("room_id"),
             event_type, json.dumps(event_data)),
        )

        events.append({
            "agent_name": agent_name,
            "event_type": event_type,
            "state": new_state,
        })

        await sse.broadcast("office.position_updated", {
            "agent_id": pos_data["agent_id"],
            "name": agent_name,
            "room_id": pos_data.get("room_id"),
            "x": new_x,
            "y": new_y,
            "state": new_state,
        })

    await db.commit()
    return {"status": "ok", "events": events}
