"""Autopilot router — autonomous pipeline management."""
import json
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from database import get_db
from services.autopilot_engine import (
    build_pipeline_steps, evaluate_quality_gate, execute_step_with_ai,
    PIPELINE_TEMPLATES, generate_run_id, generate_step_id,
)
from models.phase4 import AutopilotRunCreate, AutopilotRunUpdate, AutopilotApproval

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])


@router.get("/templates")
async def list_templates():
    """List available pipeline templates."""
    return {k: {"name": v["name"], "steps": len(v["steps"]), "quality_gates": len(v["quality_gates"])} for k, v in PIPELINE_TEMPLATES.items()}


@router.get("/runs")
async def list_runs(status: str | None = None, limit: int = 50):
    """List autopilot runs."""
    db = await get_db()
    query = "SELECT * FROM autopilot_runs"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = await db.execute_fetchall(query, params)
    return [dict(r) for r in rows]


@router.post("/runs")
async def create_run(body: AutopilotRunCreate):
    """Create a new autopilot run from a template."""
    db = await get_db()
    run_id = generate_run_id()
    steps = build_pipeline_steps(body.template, body.objective)
    template = PIPELINE_TEMPLATES.get(body.template, PIPELINE_TEMPLATES["feature"])
    quality_gates = template.get("quality_gates", [])

    await db.execute(
        """INSERT INTO autopilot_runs
        (id, name, objective, status, pipeline_config, quality_gates, steps, current_step, total_steps, approval_required)
        VALUES (?, ?, ?, 'draft', ?, ?, ?, 0, ?, ?)""",
        (run_id, body.name, body.objective, json.dumps(body.pipeline_config),
         json.dumps(quality_gates), json.dumps(steps), len(steps), 1 if body.approval_required else 0),
    )

    # Insert steps
    for i, step in enumerate(steps):
        await db.execute(
            """INSERT INTO autopilot_steps
            (id, run_id, step_type, name, description, status, config)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (step["id"], run_id, step["step_type"], step["name"], step["description"],
             json.dumps(step.get("config", {}))),
        )

    await db.commit()
    return {"id": run_id, "status": "draft", "steps": len(steps)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get full autopilot run with steps."""
    db = await get_db()
    async with db.execute("SELECT * FROM autopilot_runs WHERE id = ?", (run_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Run not found")
    run = dict(row)

    # Parse JSON fields
    for field in ("pipeline_config", "quality_gates", "steps"):
        if run.get(field):
            try:
                run[field] = json.loads(run[field])
            except (json.JSONDecodeError, TypeError):
                pass

    # Get steps
    step_rows = await db.execute_fetchall(
        "SELECT * FROM autopilot_steps WHERE run_id = ? ORDER BY created_at", (run_id,)
    )
    run["step_details"] = [dict(s) for s in step_rows]
    for step in run["step_details"]:
        for field in ("config", "input_data", "output_data", "gate_result"):
            if step.get(field):
                try:
                    step[field] = json.loads(step[field])
                except (json.JSONDecodeError, TypeError):
                    pass
    return run


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: str, body: AutopilotApproval):
    """Approve an autopilot run for execution."""
    db = await get_db()
    async with db.execute("SELECT status FROM autopilot_runs WHERE id = ?", (run_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Run not found")
    if dict(row)["status"] != "draft":
        raise HTTPException(400, "Only draft runs can be approved")

    now = datetime.utcnow().isoformat()
    await db.execute(
        "UPDATE autopilot_runs SET status = 'approved', approved_by = ?, approved_at = ? WHERE id = ?",
        (body.approved_by, now, run_id),
    )
    await db.commit()
    return {"status": "approved", "approved_by": body.approved_by}


@router.post("/runs/{run_id}/start")
async def start_run(run_id: str):
    """Start executing an autopilot run (must be approved or have approval not required)."""
    db = await get_db()
    async with db.execute("SELECT * FROM autopilot_runs WHERE id = ?", (run_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Run not found")
    run = dict(row)

    if run["status"] == "running":
        raise HTTPException(400, "Run is already running")
    if run["approval_required"] and run["status"] != "approved":
        raise HTTPException(400, "Run requires approval before starting")

    now = datetime.utcnow().isoformat()
    await db.execute(
        "UPDATE autopilot_runs SET status = 'running', started_at = ? WHERE id = ?",
        (now, run_id),
    )
    await db.execute(
        "UPDATE autopilot_steps SET status = 'in_progress' WHERE run_id = ? AND step_type = 'research'",
        (run_id,),
    )
    await db.commit()
    return {"status": "running", "started_at": now}


@router.post("/runs/{run_id}/execute-step/{step_id}")
async def execute_step(run_id: str, step_id: str):
    """Execute a single step of an autopilot run using AI."""
    db = await get_db()

    # Verify run is running
    async with db.execute("SELECT status, objective, quality_gates FROM autopilot_runs WHERE id = ?", (run_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Run not found")
    run = dict(row)
    if run["status"] != "running":
        raise HTTPException(400, "Run is not in running state")

    # Get step
    async with db.execute("SELECT * FROM autopilot_steps WHERE id = ? AND run_id = ?", (step_id, run_id)) as cur:
        step_row = await cur.fetchone()
    if not step_row:
        raise HTTPException(404, "Step not found")
    step = dict(step_row)
    for f in ("config", "input_data", "output_data"):
        if step.get(f):
            try:
                step[f] = json.loads(step[f])
            except (json.JSONDecodeError, TypeError):
                pass

    # Mark step in_progress
    now = datetime.utcnow().isoformat()
    await db.execute(
        "UPDATE autopilot_steps SET status = 'in_progress', started_at = ? WHERE id = ?",
        (now, step_id),
    )

    # Execute with AI
    context = {"objective": run["objective"], "previous_outputs": {}}
    result = await execute_step_with_ai(step, context)

    # Update step with results
    completed = datetime.utcnow().isoformat()
    await db.execute(
        """UPDATE autopilot_steps SET
        status = 'completed', output_data = ?, quality_score = ?,
        tokens_used = ?, cost = ?, completed_at = ?
        WHERE id = ?""",
        (json.dumps(result.get("output_data", {})), result.get("quality_score", 0.7),
         result.get("tokens_used", 0), result.get("cost", 0), completed, step_id),
    )

    # Check quality gates
    gates = json.loads(run.get("quality_gates", "[]")) if isinstance(run.get("quality_gates"), str) else run.get("quality_gates", [])
    step_index = step.get("id", "")  # We'll check by position
    gate_results = []
    for gate in gates:
        if gate.get("after_step", -1) == step.get("order", -1):
            gate_result = await evaluate_quality_gate(gate, result)
            gate_results.append(gate_result)
            if not gate_result["passed"]:
                # Gate failed — pause the run
                await db.execute(
                    "UPDATE autopilot_runs SET status = 'paused' WHERE id = ?", (run_id,),
                )
                await db.execute(
                    "UPDATE autopilot_steps SET gate_result = ? WHERE id = ?",
                    (json.dumps(gate_result), step_id),
                )

    if gate_results:
        await db.execute(
            "UPDATE autopilot_steps SET gate_result = ? WHERE id = ?",
            (json.dumps(gate_results), step_id),
        )

    # Record cost
    from services.cost_tracker import build_cost_record
    cost_rec = build_cost_record(
        run_id=run_id, model="gemini-2.0-flash-lite",
        operation=f"autopilot:{step['step_type']}",
        input_tokens=result.get("tokens_used", 0) // 2,
        output_tokens=result.get("tokens_used", 0) // 2,
    )
    await db.execute(
        """INSERT INTO cost_records (id, agent_id, task_id, run_id, model, operation, input_tokens, output_tokens, total_tokens, cost, currency, recorded_at)
        VALUES (?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (cost_rec["id"], cost_rec["run_id"], cost_rec["model"], cost_rec["operation"],
         cost_rec["input_tokens"], cost_rec["output_tokens"], cost_rec["total_tokens"],
         cost_rec["cost"], cost_rec["currency"], cost_rec["recorded_at"]),
    )

    # Update run totals
    await db.execute(
        """UPDATE autopilot_runs SET
        actual_cost = (SELECT COALESCE(SUM(cost), 0) FROM cost_records WHERE run_id = ?),
        tokens_used = (SELECT COALESCE(SUM(total_tokens), 0) FROM cost_records WHERE run_id = ?),
        current_step = current_step + 1,
        updated_at = ?
        WHERE id = ?""",
        (run_id, run_id, datetime.utcnow().isoformat(), run_id),
    )

    await db.commit()
    return {"step_id": step_id, "status": "completed", "quality_score": result.get("quality_score"), "gate_results": gate_results}


@router.post("/runs/{run_id}/complete")
async def complete_run(run_id: str):
    """Mark a run as completed."""
    db = await get_db()
    now = datetime.utcnow().isoformat()
    await db.execute(
        "UPDATE autopilot_runs SET status = 'completed', completed_at = ?, updated_at = ? WHERE id = ?",
        (now, now, run_id),
    )
    await db.commit()
    return {"status": "completed"}


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    """Delete an autopilot run and its steps."""
    db = await get_db()
    await db.execute("DELETE FROM autopilot_steps WHERE run_id = ?", (run_id,))
    await db.execute("DELETE FROM autopilot_runs WHERE id = ?", (run_id,))
    await db.commit()
    return {"deleted": True}
