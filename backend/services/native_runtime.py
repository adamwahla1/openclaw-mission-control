"""Native Mission Control runtime and Project Builder v1 workflow."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any

import aiosqlite

from database import get_db
from services.providers import PROVIDERS, get_model_config, record_provider_cost
from services.sse_broadcaster import sse

logger = logging.getLogger(__name__)

try:  # Optional dependency: installed for the power layer, not required to boot.
    import pydantic_ai  # noqa: F401

    PYDANTIC_AI_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment packages
    PYDANTIC_AI_AVAILABLE = False

try:  # Optional dependency: Project Builder can graduate to a durable graph.
    import langgraph  # noqa: F401

    LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment packages
    LANGGRAPH_AVAILABLE = False

PROJECT_BUILDER_STEPS = [
    ("intake", "Intake", "planner"),
    ("plan", "Implementation Plan", "planner"),
    ("research", "Context Research", "researcher"),
    ("build_draft", "Draft Build Plan", "builder"),
    ("review", "Critical Review", "reviewer"),
    ("test_plan", "Validation Plan", "reviewer"),
    ("report", "Final Report", "reporter"),
]


class NativeMissionControlRuntime:
    name = "native"
    label = "Native Mission Control"

    def __init__(self) -> None:
        self._active_tasks: dict[str, asyncio.Task] = {}

    async def status(self, db: aiosqlite.Connection) -> dict[str, Any]:
        async with db.execute("SELECT COUNT(*) AS count FROM agents") as cursor:
            agent_count = (await cursor.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) AS count FROM runs WHERE status IN ('queued','running','awaiting_approval')") as cursor:
            active_runs = (await cursor.fetchone())["count"]
        async with db.execute("SELECT COUNT(*) AS count FROM provider_configs WHERE provider = 'openrouter' AND enabled = 1") as cursor:
            providers = (await cursor.fetchone())["count"]
        return {
            "name": self.name,
            "label": self.label,
            "ready": True,
            "agent_count": agent_count,
            "active_runs": active_runs,
            "providers_configured": providers,
            "pydantic_ai_available": PYDANTIC_AI_AVAILABLE,
            "langgraph_available": LANGGRAPH_AVAILABLE,
            "supervision": "approval_required_for_write_tools",
        }

    async def list_agents(self, db: aiosqlite.Connection) -> list[dict[str, Any]]:
        rows = await db.execute_fetchall("SELECT * FROM agents ORDER BY created_at DESC")
        return [_row_to_agent(row) for row in rows]

    async def create_agent(
        self,
        db: aiosqlite.Connection,
        name: str,
        role: str = "",
        soul_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        agent_id = str(uuid.uuid4())
        soul = soul_config or {}
        await db.execute(
            """
            INSERT INTO agents (id, gateway_agent_id, name, role, soul_config, status)
            VALUES (?, NULL, ?, ?, ?, 'idle')
            """,
            (agent_id, name, role, json.dumps(soul)),
        )
        await db.commit()
        agent = await self.get_agent(db, agent_id)
        await sse.broadcast("agent.created", agent)
        return agent

    async def get_agent(self, db: aiosqlite.Connection, agent_id: str) -> dict[str, Any]:
        async with db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            raise ValueError("Agent not found")
        return _row_to_agent(row)

    async def start_session(
        self,
        db: aiosqlite.Connection,
        title: str,
        agent_id: str | None = None,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        await db.execute(
            """
            INSERT INTO sessions (id, agent_id, task_id, title, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, agent_id, task_id, title or "Session", json.dumps(metadata or {})),
        )
        await db.commit()
        return await self.get_session(db, session_id)

    async def get_session(self, db: aiosqlite.Connection, session_id: str) -> dict[str, Any]:
        async with db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            raise ValueError("Session not found")
        return _parse_json_fields(dict(row), ["metadata"])

    async def send_message(
        self,
        db: aiosqlite.Connection,
        session_id: str,
        content: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        session = await self.get_session(db, session_id)
        agent_id = agent_id or session.get("agent_id")
        run = await self.start_run(
            db,
            run_type="agent_message",
            title=f"Message: {session['title']}",
            objective=content,
            task_id=session.get("task_id"),
            session_id=session_id,
            metadata={"agent_id": agent_id},
            autostart=False,
        )
        await self._insert_message(db, session_id, run["id"], agent_id, "user", content)
        task = asyncio.create_task(self._execute_agent_message(run["id"], session_id, content, agent_id))
        self._active_tasks[run["id"]] = task
        return run

    async def start_run(
        self,
        db: aiosqlite.Connection,
        run_type: str,
        title: str,
        objective: str,
        task_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        autostart: bool = True,
    ) -> dict[str, Any]:
        run_id = f"run-{uuid.uuid4().hex[:10]}"
        await db.execute(
            """
            INSERT INTO runs (id, runtime, run_type, title, objective, task_id, session_id, metadata)
            VALUES (?, 'native', ?, ?, ?, ?, ?, ?)
            """,
            (run_id, run_type, title, objective, task_id, session_id, json.dumps(metadata or {})),
        )
        if run_type == "project_builder":
            for index, (step_key, step_title, role) in enumerate(PROJECT_BUILDER_STEPS):
                await db.execute(
                    """
                    INSERT INTO run_steps (id, run_id, step_key, title, agent_role, order_index)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (f"step-{uuid.uuid4().hex[:10]}", run_id, step_key, step_title, role, index),
                )
        await db.commit()
        await self._event(db, run_id, "run.created", title="Run created", content=objective)
        run = await self.get_run(db, run_id)
        if autostart and run_type == "project_builder":
            task = asyncio.create_task(self._execute_project_builder(run_id))
            self._active_tasks[run_id] = task
        return run

    async def get_run(self, db: aiosqlite.Connection, run_id: str) -> dict[str, Any]:
        async with db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            raise ValueError("Run not found")
        run = _parse_json_fields(dict(row), ["metadata"])
        steps = await db.execute_fetchall("SELECT * FROM run_steps WHERE run_id = ? ORDER BY order_index", (run_id,))
        run["steps"] = [_parse_json_fields(dict(step), ["input", "output"]) for step in steps]
        return run

    async def list_runs(self, db: aiosqlite.Connection, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM runs"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = await db.execute_fetchall(query, params)
        return [_parse_json_fields(dict(row), ["metadata"]) for row in rows]

    async def get_events(self, db: aiosqlite.Connection, run_id: str) -> list[dict[str, Any]]:
        rows = await db.execute_fetchall(
            "SELECT * FROM run_events WHERE run_id = ? ORDER BY sequence ASC, created_at ASC",
            (run_id,),
        )
        return [_parse_json_fields(dict(row), ["data"]) for row in rows]

    async def cancel_run(self, db: aiosqlite.Connection, run_id: str) -> dict[str, Any]:
        task = self._active_tasks.pop(run_id, None)
        if task and not task.done():
            task.cancel()
        await db.execute(
            "UPDATE runs SET status = 'cancelled', updated_at = datetime('now'), completed_at = datetime('now') WHERE id = ?",
            (run_id,),
        )
        await db.commit()
        await self._event(db, run_id, "run.cancelled", title="Run cancelled")
        return await self.get_run(db, run_id)

    async def resume_run(self, db: aiosqlite.Connection, run_id: str) -> dict[str, Any]:
        run = await self.get_run(db, run_id)
        if run["run_type"] == "project_builder" and run["status"] == "awaiting_approval":
            task = asyncio.create_task(self._continue_project_builder_after_approval(run_id))
            self._active_tasks[run_id] = task
            return run
        await self._event(db, run_id, "run.resume_ignored", title="Run does not need resume")
        return run

    async def _execute_agent_message(self, run_id: str, session_id: str, prompt: str, agent_id: str | None) -> None:
        db = await get_db()
        try:
            await self._mark_run(db, run_id, "running", current_step="agent_message", started=True)
            await self._event(db, run_id, "agent.started", role="assistant", title="Agent started")
            response = await self._call_model(db, "cheap_fast", prompt, run_id, agent_id=agent_id, operation="agent.message")
            await self._insert_message(db, session_id, run_id, agent_id, "assistant", response)
            await self._event(db, run_id, "message.completed", role="assistant", title="Response completed", content=response)
            await self._mark_run(db, run_id, "completed", result=response, completed=True)
        except Exception as exc:
            await self._fail_run(db, run_id, exc)
        finally:
            self._active_tasks.pop(run_id, None)

    async def _execute_project_builder(self, run_id: str) -> None:
        db = await get_db()
        try:
            run = await self.get_run(db, run_id)
            objective = run["objective"]
            await self._mark_run(db, run_id, "running", current_step="intake", started=True)
            await self._complete_step(db, run_id, "intake", "Captured objective and prepared supervised project workflow.")

            await self._mark_run(db, run_id, "running", current_step="plan")
            plan = await self._call_model(
                db,
                "planner",
                _project_prompt("plan", objective),
                run_id,
                operation="project_builder.plan",
            )
            await self._complete_step(db, run_id, "plan", plan)

            await self._mark_run(db, run_id, "running", current_step="research")
            research = await self._call_model(
                db,
                "cheap_fast",
                _project_prompt("research", objective, plan),
                run_id,
                operation="project_builder.research",
            )
            await self._complete_step(db, run_id, "research", research)

            await self._mark_run(db, run_id, "running", current_step="build_draft")
            draft = await self._call_model(
                db,
                "builder",
                _project_prompt("draft", objective, plan, research),
                run_id,
                operation="project_builder.draft",
            )
            await self._complete_step(db, run_id, "build_draft", draft)
            await self._request_tool_approval(db, run_id, "repo.draft_patch", "write", draft)
        except Exception as exc:
            await self._fail_run(db, run_id, exc)
            self._active_tasks.pop(run_id, None)

    async def _continue_project_builder_after_approval(self, run_id: str) -> None:
        db = await get_db()
        try:
            approved = await self._has_approved_write_action(db, run_id)
            if not approved:
                await self._event(db, run_id, "approval.waiting", title="Waiting for approval")
                return
            run = await self.get_run(db, run_id)
            objective = run["objective"]
            prior = await self._step_outputs(db, run_id)
            await self._mark_run(db, run_id, "running", current_step="review")
            review = await self._call_model(
                db,
                "reviewer",
                _project_prompt("review", objective, prior.get("plan", ""), prior.get("build_draft", "")),
                run_id,
                operation="project_builder.review",
            )
            await self._complete_step(db, run_id, "review", review)

            await self._mark_run(db, run_id, "running", current_step="test_plan")
            test_plan = await self._call_model(
                db,
                "reviewer",
                _project_prompt("test", objective, prior.get("build_draft", ""), review),
                run_id,
                operation="project_builder.test_plan",
            )
            await self._complete_step(db, run_id, "test_plan", test_plan)

            await self._mark_run(db, run_id, "running", current_step="report")
            final_report = _final_project_report(objective, prior, review, test_plan)
            await self._complete_step(db, run_id, "report", final_report)
            await self._save_artifact(db, run_id, run.get("task_id"), "final_report", "Project Builder Report", final_report)
            if run.get("task_id"):
                await db.execute(
                    "UPDATE tasks SET final_report = ?, status = 'review', updated_at = datetime('now') WHERE id = ?",
                    (final_report, run["task_id"]),
                )
                await db.commit()
            await self._mark_run(db, run_id, "completed", result=final_report, completed=True)
            await self._event(db, run_id, "run.completed", title="Project Builder completed", content=final_report[:1000])
        except Exception as exc:
            await self._fail_run(db, run_id, exc)
        finally:
            self._active_tasks.pop(run_id, None)

    async def _call_model(
        self,
        db: aiosqlite.Connection,
        purpose: str,
        prompt: str,
        run_id: str,
        agent_id: str | None = None,
        operation: str = "model.call",
    ) -> str:
        cfg = await get_model_config(db, purpose)
        provider_name = cfg.get("provider", "openrouter")
        provider = PROVIDERS.get(provider_name)
        if not provider:
            return _offline_response(purpose, prompt)
        try:
            await self._event(db, run_id, "model.started", title=f"Calling {cfg.get('model')}", data={"purpose": purpose})
            response = await provider.chat(
                db,
                messages=[{"role": "user", "content": prompt}],
                model=cfg.get("model", "openrouter/auto"),
                temperature=float(cfg.get("temperature", 0.4)),
                max_tokens=int(cfg.get("max_tokens", 2048)),
                routing_policy=cfg.get("routing_policy", "pinned"),
            )
            await record_provider_cost(db, response, operation=operation, agent_id=agent_id, run_id=run_id)
            await self._event(
                db,
                run_id,
                "model.completed",
                title=f"Model completed: {response.actual_model}",
                data={
                    "provider": response.provider,
                    "requested_model": response.requested_model,
                    "actual_model": response.actual_model,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "total_tokens": response.total_tokens,
                    "latency_ms": response.latency_ms,
                    "cost_usd": response.cost_usd,
                },
            )
            return response.content or _offline_response(purpose, prompt)
        except Exception as exc:
            logger.warning("Provider call failed; using offline response: %s", exc)
            await self._event(db, run_id, "model.fallback", title="Provider fallback", content=str(exc))
            return _offline_response(purpose, prompt)

    async def _insert_message(
        self,
        db: aiosqlite.Connection,
        session_id: str,
        run_id: str,
        agent_id: str | None,
        role: str,
        content: str,
    ) -> None:
        await db.execute(
            """
            INSERT INTO messages (id, session_id, run_id, agent_id, role, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), session_id, run_id, agent_id, role, content),
        )
        await db.commit()

    async def _complete_step(self, db: aiosqlite.Connection, run_id: str, step_key: str, output: str) -> None:
        async with db.execute(
            "SELECT id, title FROM run_steps WHERE run_id = ? AND step_key = ?",
            (run_id, step_key),
        ) as cursor:
            row = await cursor.fetchone()
        step_id = row["id"] if row else None
        title = row["title"] if row else step_key
        if step_id:
            await db.execute(
                """
                UPDATE run_steps
                SET status = 'completed', output = ?, started_at = COALESCE(started_at, datetime('now')),
                    completed_at = datetime('now')
                WHERE id = ?
                """,
                (json.dumps({"content": output}), step_id),
            )
            await db.commit()
        await self._event(db, run_id, "step.completed", step_id=step_id, title=title, content=output)

    async def _request_tool_approval(
        self,
        db: aiosqlite.Connection,
        run_id: str,
        tool_name: str,
        risk_level: str,
        draft: str,
    ) -> None:
        approval_id = f"approval-{uuid.uuid4().hex[:10]}"
        payload = {"tool_name": tool_name, "risk_level": risk_level, "draft_preview": draft[:2000]}
        await db.execute(
            """
            INSERT INTO approvals
                (id, action_type, target_type, target_id, requested_by, status, run_id, tool_name,
                 risk_level, request_payload, created_at)
            VALUES (?, 'tool.execute', 'run', ?, 'native-runtime', 'pending', ?, ?, ?, ?, datetime('now'))
            """,
            (approval_id, run_id, run_id, tool_name, risk_level, json.dumps(payload)),
        )
        await db.execute(
            "UPDATE runs SET status = 'awaiting_approval', current_step = 'approval', updated_at = datetime('now') WHERE id = ?",
            (run_id,),
        )
        await db.commit()
        await self._event(
            db,
            run_id,
            "approval.requested",
            title="Approval required",
            content="Project Builder drafted a write-level action and paused for review.",
            data={"approval_id": approval_id, **payload},
        )

    async def _has_approved_write_action(self, db: aiosqlite.Connection, run_id: str) -> bool:
        async with db.execute(
            "SELECT id FROM approvals WHERE run_id = ? AND status = 'approved' LIMIT 1",
            (run_id,),
        ) as cursor:
            return bool(await cursor.fetchone())

    async def _step_outputs(self, db: aiosqlite.Connection, run_id: str) -> dict[str, str]:
        rows = await db.execute_fetchall("SELECT step_key, output FROM run_steps WHERE run_id = ?", (run_id,))
        outputs: dict[str, str] = {}
        for row in rows:
            try:
                payload = json.loads(row["output"] or "{}")
                outputs[row["step_key"]] = payload.get("content", "")
            except Exception:
                outputs[row["step_key"]] = row["output"] or ""
        return outputs

    async def _save_artifact(
        self,
        db: aiosqlite.Connection,
        run_id: str,
        task_id: str | None,
        artifact_type: str,
        title: str,
        content: str,
    ) -> None:
        await db.execute(
            """
            INSERT INTO artifacts (id, run_id, task_id, artifact_type, title, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (f"artifact-{uuid.uuid4().hex[:10]}", run_id, task_id, artifact_type, title, content),
        )
        await db.commit()

    async def _mark_run(
        self,
        db: aiosqlite.Connection,
        run_id: str,
        status: str,
        current_step: str | None = None,
        result: str | None = None,
        started: bool = False,
        completed: bool = False,
    ) -> None:
        updates = ["status = ?", "updated_at = datetime('now')"]
        params: list[Any] = [status]
        if current_step is not None:
            updates.append("current_step = ?")
            params.append(current_step)
        if result is not None:
            updates.append("result = ?")
            params.append(result)
        if started:
            updates.append("started_at = COALESCE(started_at, datetime('now'))")
        if completed:
            updates.append("completed_at = datetime('now')")
        params.append(run_id)
        await db.execute(f"UPDATE runs SET {', '.join(updates)} WHERE id = ?", params)
        await db.commit()
        await self._event(db, run_id, f"run.{status}", title=f"Run {status}", data={"current_step": current_step})

    async def _fail_run(self, db: aiosqlite.Connection, run_id: str, exc: Exception) -> None:
        message = str(exc)
        await db.execute(
            "UPDATE runs SET status = 'failed', error = ?, updated_at = datetime('now'), completed_at = datetime('now') WHERE id = ?",
            (message, run_id),
        )
        await db.commit()
        await self._event(db, run_id, "run.failed", title="Run failed", content=message)

    async def _event(
        self,
        db: aiosqlite.Connection,
        run_id: str,
        event_type: str,
        step_id: str | None = None,
        role: str = "",
        agent_id: str | None = None,
        title: str = "",
        content: str = "",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with db.execute("SELECT COALESCE(MAX(sequence), 0) + 1 AS next_seq FROM run_events WHERE run_id = ?", (run_id,)) as cursor:
            sequence = (await cursor.fetchone())["next_seq"]
        event = {
            "id": f"event-{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "step_id": step_id,
            "event_type": event_type,
            "role": role,
            "agent_id": agent_id,
            "title": title,
            "content": content,
            "data": data or {},
            "sequence": sequence,
            "created_at": datetime.utcnow().isoformat(),
        }
        await db.execute(
            """
            INSERT INTO run_events
                (id, run_id, step_id, event_type, role, agent_id, title, content, data, sequence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["id"],
                run_id,
                step_id,
                event_type,
                role,
                agent_id,
                title,
                content,
                json.dumps(data or {}),
                sequence,
                event["created_at"],
            ),
        )
        await db.commit()
        await sse.broadcast("run.event", event)
        return event


native_runtime = NativeMissionControlRuntime()


def _row_to_agent(row: Any) -> dict[str, Any]:
    data = dict(row)
    try:
        data["soul_config"] = json.loads(data.get("soul_config") or "{}")
    except (json.JSONDecodeError, TypeError):
        data["soul_config"] = {}
    return data


def _parse_json_fields(data: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    for field in fields:
        try:
            data[field] = json.loads(data.get(field) or "{}")
        except (json.JSONDecodeError, TypeError):
            data[field] = {} if field != "data" else {}
    return data


def _project_prompt(stage: str, objective: str, context_a: str = "", context_b: str = "") -> str:
    prompts = {
        "plan": "Create a concise implementation plan with milestones, risks, and acceptance checks.",
        "research": "Inspect the available context and identify what must be understood before implementation.",
        "draft": "Draft the implementation approach and patch strategy. Do not claim files were changed.",
        "review": "Review the draft critically for missing tests, safety, migration risk, and product quality.",
        "test": "Create a validation plan with concrete test commands and manual scenarios.",
    }
    return (
        f"Mission Control Project Builder stage: {stage}\n"
        f"Objective:\n{objective}\n\n"
        f"Primary context:\n{context_a[:4000]}\n\n"
        f"Secondary context:\n{context_b[:4000]}\n\n"
        f"Instruction: {prompts.get(stage, 'Produce a useful project-builder output.')}\n"
        "Be specific, supervised, and honest about what has not been executed."
    )


def _offline_response(purpose: str, prompt: str) -> str:
    trimmed = prompt.strip().splitlines()[0][:160] if prompt.strip() else "the request"
    return (
        f"## Offline {purpose.replace('_', ' ').title()} Draft\n\n"
        f"Mission Control is running in native mode, but no working model provider is configured yet. "
        f"Here is a structured placeholder for: {trimmed}\n\n"
        "- Configure OpenRouter in Settings to turn this into a live model-generated result.\n"
        "- This run still records durable events, approvals, and artifacts so the control-room flow can be tested.\n"
    )


def _final_project_report(objective: str, prior: dict[str, str], review: str, test_plan: str) -> str:
    return f"""# Project Builder Report

## Objective
{objective}

## Plan
{prior.get('plan', '').strip() or 'No plan output recorded.'}

## Research
{prior.get('research', '').strip() or 'No research output recorded.'}

## Draft Build Strategy
{prior.get('build_draft', '').strip() or 'No draft output recorded.'}

## Review
{review.strip()}

## Validation Plan
{test_plan.strip()}

## Notes
- This is a supervised native Mission Control run.
- Write-level actions are paused behind approvals before implementation.
- OpenRouter configuration upgrades placeholder sections into live model output.
"""
