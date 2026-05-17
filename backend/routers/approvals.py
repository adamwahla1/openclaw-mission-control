"""Human approval endpoints for supervised native runtime actions."""
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db
from services.runtime_registry import runtime_registry
from services.sse_broadcaster import sse

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class ApprovalCreateRequest(BaseModel):
    action_type: str
    target_type: str = "run"
    target_id: str = ""
    run_id: str | None = None
    tool_name: str = ""
    risk_level: str = "read-only"
    requested_by: str = "user"
    request_payload: dict[str, Any] = {}


class ApprovalDecisionRequest(BaseModel):
    decided_by: str = "user"
    notes: str = ""
    decision_payload: dict[str, Any] = {}


@router.get("")
async def list_approvals(status: str | None = "pending"):
    db = await get_db()
    query = "SELECT * FROM approvals"
    params: list[Any] = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    rows = await db.execute_fetchall(query, params)
    return [_parse(row) for row in rows]


@router.post("", status_code=201)
async def create_approval(body: ApprovalCreateRequest):
    db = await get_db()
    approval_id = f"approval-{uuid.uuid4().hex[:10]}"
    await db.execute(
        """
        INSERT INTO approvals
            (id, action_type, target_type, target_id, requested_by, status, run_id, tool_name,
             risk_level, request_payload, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, datetime('now'))
        """,
        (
            approval_id,
            body.action_type,
            body.target_type,
            body.target_id,
            body.requested_by,
            body.run_id,
            body.tool_name,
            body.risk_level,
            json.dumps(body.request_payload),
        ),
    )
    await db.commit()
    approval = await _get(db, approval_id)
    await sse.broadcast("approval.created", approval)
    return approval


@router.post("/{approval_id}/approve")
async def approve(approval_id: str, body: ApprovalDecisionRequest):
    return await _decide(approval_id, "approved", body)


@router.post("/{approval_id}/reject")
async def reject(approval_id: str, body: ApprovalDecisionRequest):
    return await _decide(approval_id, "rejected", body)


async def _decide(approval_id: str, status: str, body: ApprovalDecisionRequest):
    db = await get_db()
    await _get(db, approval_id)
    await db.execute(
        """
        UPDATE approvals
        SET status = ?, reviewer_notes = ?, decision_payload = ?, decided_at = datetime('now')
        WHERE id = ?
        """,
        (status, body.notes, json.dumps({"decided_by": body.decided_by, **body.decision_payload}), approval_id),
    )
    await db.commit()
    approval = await _get(db, approval_id)
    await sse.broadcast(f"approval.{status}", approval)
    if approval.get("run_id"):
        if status == "approved":
            await runtime_registry.native.resume_run(db, approval["run_id"])
        elif status == "rejected":
            await runtime_registry.native.cancel_run(db, approval["run_id"])
    return approval


async def _get(db, approval_id: str) -> dict[str, Any]:
    async with db.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Approval not found")
    return _parse(row)


def _parse(row) -> dict[str, Any]:
    data = dict(row)
    for field in ("request_payload", "decision_payload"):
        try:
            data[field] = json.loads(data.get(field) or "{}")
        except (json.JSONDecodeError, TypeError):
            data[field] = {}
    return data
