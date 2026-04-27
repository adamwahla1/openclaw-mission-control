"""Cost Dashboard router — per-agent, per-model, per-task cost tracking."""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from database import get_db
from services.cost_tracker import build_cost_record, get_cost_summary, estimate_cost, MODEL_COSTS
from models.phase4 import CostRecordCreate, CostSummaryRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.get("/summary")
async def cost_summary(group_by: str = "agent", days: int = 30):
    """Get aggregated cost summary."""
    db = await get_db()
    summary = await get_cost_summary(db, group_by, days)

    # Add totals
    total_cost = sum(s.get("total_cost", 0) for s in summary)
    total_tokens = sum(s.get("total_tokens", 0) for s in summary)

    return {
        "group_by": group_by,
        "days": days,
        "total_cost": round(total_cost, 6),
        "total_tokens": total_tokens,
        "records": len(summary),
        "breakdown": summary,
    }


@router.get("/records")
async def list_records(
    agent_id: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    model: str | None = None,
    limit: int = 100,
):
    """List individual cost records."""
    db = await get_db()
    query = "SELECT cr.*, a.name as agent_name FROM cost_records cr LEFT JOIN agents a ON a.id = cr.agent_id"
    params = []
    conditions = []
    if agent_id:
        conditions.append("cr.agent_id = ?")
        params.append(agent_id)
    if task_id:
        conditions.append("cr.task_id = ?")
        params.append(task_id)
    if run_id:
        conditions.append("cr.run_id = ?")
        params.append(run_id)
    if model:
        conditions.append("cr.model = ?")
        params.append(model)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY cr.recorded_at DESC LIMIT ?"
    params.append(limit)
    rows = await db.execute_fetchall(query, params)
    return [dict(r) for r in rows]


@router.post("/records")
async def create_record(body: CostRecordCreate):
    """Manually record a cost entry."""
    db = await get_db()
    rec = build_cost_record(
        agent_id=body.agent_id,
        task_id=body.task_id,
        run_id=body.run_id,
        model=body.model,
        operation=body.operation,
        input_tokens=body.input_tokens,
        output_tokens=body.output_tokens,
    )
    await db.execute(
        """INSERT INTO cost_records (id, agent_id, task_id, run_id, model, operation, input_tokens, output_tokens, total_tokens, cost, currency, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (rec["id"], rec["agent_id"], rec["task_id"], rec["run_id"], rec["model"],
         rec["operation"], rec["input_tokens"], rec["output_tokens"], rec["total_tokens"],
         rec["cost"], rec["currency"], rec["recorded_at"]),
    )
    await db.commit()
    return rec


@router.get("/models")
async def list_model_costs():
    """List available models with their cost rates."""
    return {
        "models": [
            {"model": k, "input_per_1m": v["input"], "output_per_1m": v["output"]}
            for k, v in MODEL_COSTS.items()
        ]
    }


@router.post("/estimate")
async def estimate_cost_endpoint(body: CostRecordCreate):
    """Estimate cost for a given model and token usage."""
    cost = estimate_cost(body.model, body.input_tokens, body.output_tokens)
    return {
        "model": body.model,
        "input_tokens": body.input_tokens,
        "output_tokens": body.output_tokens,
        "total_tokens": body.input_tokens + body.output_tokens,
        "estimated_cost_usd": cost,
    }


@router.get("/dashboard")
async def cost_dashboard(days: int = 30):
    """Full dashboard data: summary by agent, model, and daily trend."""
    db = await get_db()

    by_agent = await get_cost_summary(db, "agent", days)
    by_model = await get_cost_summary(db, "model", days)
    by_day = await get_cost_summary(db, "day", days)

    total_cost = sum(s.get("total_cost", 0) for s in by_agent)
    total_tokens = sum(s.get("total_tokens", 0) for s in by_agent)

    # Recent records
    recent = await db.execute_fetchall(
        "SELECT cr.*, a.name as agent_name FROM cost_records cr LEFT JOIN agents a ON a.id = cr.agent_id ORDER BY cr.recorded_at DESC LIMIT 10"
    )
    recent_records = [dict(r) for r in recent]

    return {
        "total_cost": round(total_cost, 6),
        "total_tokens": total_tokens,
        "days": days,
        "by_agent": by_agent,
        "by_model": by_model,
        "by_day": by_day,
        "recent_records": recent_records,
    }
