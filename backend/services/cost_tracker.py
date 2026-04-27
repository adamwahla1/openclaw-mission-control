"""Cost tracker — token and cost tracking per agent/task/model."""
import uuid
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Approximate costs per 1M tokens (USD)
MODEL_COSTS = {
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}


def generate_cost_id() -> str:
    return f"cost-{uuid.uuid4().hex[:8]}"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for a given model and token usage."""
    costs = MODEL_COSTS.get(model, {"input": 0.50, "output": 2.00})  # Default fallback
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return round(input_cost + output_cost, 6)


def build_cost_record(
    agent_id: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    model: str = "",
    operation: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> dict:
    """Build a cost record dict ready for insertion."""
    total_tokens = input_tokens + output_tokens
    cost = estimate_cost(model, input_tokens, output_tokens)
    return {
        "id": generate_cost_id(),
        "agent_id": agent_id,
        "task_id": task_id,
        "run_id": run_id,
        "model": model,
        "operation": operation,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
        "currency": "USD",
        "recorded_at": datetime.utcnow().isoformat(),
    }


async def get_cost_summary(db, group_by: str = "agent", days: int = 30) -> list[dict]:
    """Get aggregated cost summary grouped by the specified field."""
    if group_by == "agent":
        query = """
            SELECT
                COALESCE(a.name, cr.agent_id) as label,
                cr.agent_id,
                COUNT(*) as record_count,
                SUM(cr.total_tokens) as total_tokens,
                SUM(cr.input_tokens) as input_tokens,
                SUM(cr.output_tokens) as output_tokens,
                SUM(cr.cost) as total_cost,
                AVG(cr.cost) as avg_cost
            FROM cost_records cr
            LEFT JOIN agents a ON a.id = cr.agent_id
            WHERE cr.recorded_at >= datetime('now', ?)
            GROUP BY cr.agent_id
            ORDER BY total_cost DESC
        """
    elif group_by == "model":
        query = """
            SELECT
                cr.model as label,
                NULL as agent_id,
                COUNT(*) as record_count,
                SUM(cr.total_tokens) as total_tokens,
                SUM(cr.input_tokens) as input_tokens,
                SUM(cr.output_tokens) as output_tokens,
                SUM(cr.cost) as total_cost,
                AVG(cr.cost) as avg_cost
            FROM cost_records cr
            WHERE cr.recorded_at >= datetime('now', ?)
            GROUP BY cr.model
            ORDER BY total_cost DESC
        """
    elif group_by == "task":
        query = """
            SELECT
                COALESCE(t.title, cr.task_id) as label,
                cr.task_id as agent_id,
                COUNT(*) as record_count,
                SUM(cr.total_tokens) as total_tokens,
                SUM(cr.input_tokens) as input_tokens,
                SUM(cr.output_tokens) as output_tokens,
                SUM(cr.cost) as total_cost,
                AVG(cr.cost) as avg_cost
            FROM cost_records cr
            LEFT JOIN tasks t ON t.id = cr.task_id
            WHERE cr.recorded_at >= datetime('now', ?)
            GROUP BY cr.task_id
            ORDER BY total_cost DESC
        """
    else:  # day
        query = """
            SELECT
                DATE(cr.recorded_at) as label,
                NULL as agent_id,
                COUNT(*) as record_count,
                SUM(cr.total_tokens) as total_tokens,
                SUM(cr.input_tokens) as input_tokens,
                SUM(cr.output_tokens) as output_tokens,
                SUM(cr.cost) as total_cost,
                AVG(cr.cost) as avg_cost
            FROM cost_records cr
            WHERE cr.recorded_at >= datetime('now', ?)
            GROUP BY DATE(cr.recorded_at)
            ORDER BY label DESC
        """

    params = [f"-{days} days"]
    rows = await db.execute_fetchall(query, params)
    result = []
    for row in rows:
        d = dict(row)
        for k in ("total_cost", "avg_cost", "total_tokens", "input_tokens", "output_tokens"):
            if d.get(k) is not None:
                d[k] = float(d[k])
        result.append(d)
    return result
