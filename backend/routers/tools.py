"""Native runtime tool registry endpoints."""
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db

router = APIRouter(tags=["tools"])


class ToolUpdateRequest(BaseModel):
    enabled: bool | None = None
    approval_required: bool | None = None
    risk_level: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] | None = None


@router.get("/api/tools")
async def list_tools():
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM tool_registry ORDER BY name")
    return [_parse_tool(row) for row in rows]


@router.patch("/api/tools/{tool_id}")
async def update_tool(tool_id: str, body: ToolUpdateRequest):
    db = await get_db()
    async with db.execute("SELECT * FROM tool_registry WHERE id = ? OR name = ?", (tool_id, tool_id)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Tool not found")

    updates: list[str] = []
    params: list[Any] = []
    if body.enabled is not None:
        updates.append("enabled = ?")
        params.append(1 if body.enabled else 0)
    if body.approval_required is not None:
        updates.append("approval_required = ?")
        params.append(1 if body.approval_required else 0)
    if body.risk_level is not None:
        if body.risk_level not in {"read-only", "write", "destructive", "external", "financial"}:
            raise HTTPException(400, "Invalid risk level")
        updates.append("risk_level = ?")
        params.append(body.risk_level)
    if body.description is not None:
        updates.append("description = ?")
        params.append(body.description)
    if body.input_schema is not None:
        updates.append("input_schema = ?")
        params.append(json.dumps(body.input_schema))

    if updates:
        updates.append("updated_at = datetime('now')")
        params.append(row["id"])
        await db.execute(f"UPDATE tool_registry SET {', '.join(updates)} WHERE id = ?", params)
        await db.commit()

    async with db.execute("SELECT * FROM tool_registry WHERE id = ?", (row["id"],)) as cursor:
        return _parse_tool(await cursor.fetchone())


def _parse_tool(row) -> dict[str, Any]:
    data = dict(row)
    data["enabled"] = bool(data.get("enabled"))
    data["approval_required"] = bool(data.get("approval_required"))
    try:
        data["input_schema"] = json.loads(data.get("input_schema") or "{}")
    except (json.JSONDecodeError, TypeError):
        data["input_schema"] = {}
    return data
