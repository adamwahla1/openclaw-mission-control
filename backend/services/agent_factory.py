"""Intelligent Agent Factory — builds SOUL-first agents for tasks."""
import json
import logging
import uuid

from database import get_db
from services.gateway_bridge import gateway
from services.sse_broadcaster import sse

logger = logging.getLogger(__name__)

# Role detection keywords
_ROLE_KEYWORDS: dict[str, list[str]] = {
    "researcher": ["research", "find", "search", "investigate", "gather", "survey", "analyze sources"],
    "coder": ["code", "implement", "build", "develop", "program", "script", "fix", "debug", "refactor"],
    "analyst": ["analyze", "analyse", "data", "metrics", "trends", "statistics", "insights", "evaluate"],
    "writer": ["write", "document", "draft", "summarize", "report", "article", "content", "blog"],
    "planner": ["plan", "strategy", "roadmap", "design", "architect", "structure", "organize"],
    "reviewer": ["review", "audit", "check", "verify", "test", "validate", "quality", "assess"],
    "orchestrator": ["coordinate", "orchestrate", "manage", "delegate", "supervise", "direct"],
}

# Role → default skills
_ROLE_SKILLS: dict[str, list[str]] = {
    "researcher": ["web_search", "summarization", "fact_checking", "citation_tracking", "knowledge_synthesis"],
    "coder": ["code_generation", "debugging", "code_review", "testing", "refactoring", "documentation"],
    "analyst": ["data_analysis", "pattern_recognition", "statistical_inference", "visualization_design"],
    "writer": ["content_generation", "editing", "summarization", "tone_adaptation", "structured_writing"],
    "planner": ["task_decomposition", "dependency_mapping", "risk_assessment", "timeline_estimation"],
    "reviewer": ["code_review", "quality_assessment", "error_detection", "improvement_suggestions"],
    "orchestrator": ["task_dispatch", "agent_coordination", "progress_tracking", "bottleneck_detection"],
}

# Role → personality traits
_ROLE_PERSONALITY: dict[str, list[str]] = {
    "researcher": ["analytical", "thorough", "citation-aware", "curious", "detail-oriented"],
    "coder": ["precise", "efficient", "pragmatic", "solution-focused", "clean-code-advocate"],
    "analyst": ["data-driven", "objective", "pattern-seeking", "systematic", "rigorous"],
    "writer": ["articulate", "clear", "audience-aware", "structured", "creative"],
    "planner": ["strategic", "forward-thinking", "organized", "risk-aware", "methodical"],
    "reviewer": ["critical", "constructive", "thorough", "standards-driven", "improvement-oriented"],
    "orchestrator": ["decisive", "coordinating", "delegating", "monitoring", "adaptive"],
}

# Naming templates per role
_ROLE_NAMES: dict[str, list[str]] = {
    "researcher": ["Axiom", "Veritas", "Lumen", "Scrutiny"],
    "coder": ["Forge", "Nexus", "Synapse", "Cipher"],
    "analyst": ["Prism", "Lens", "Apex", "Clarity"],
    "writer": ["Quill", "Muse", "Prose", "Herald"],
    "planner": ["Atlas", "Vector", "Meridian", "Blueprint"],
    "reviewer": ["Aegis", "Sentinel", "Arbiter", "Crucible"],
    "orchestrator": ["Conductor", "Maestro", "Apex", "Director"],
}


def _infer_role(task_context: dict) -> str:
    """Infer the best agent role from task context using keyword scoring."""
    text = " ".join([
        task_context.get("title", ""),
        task_context.get("description", "") or "",
        " ".join(task_context.get("tags", [])),
    ]).lower()

    scores: dict[str, int] = {role: 0 for role in _ROLE_KEYWORDS}
    for role, keywords in _ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[role] += 1

    # Pick highest scored role; default to researcher
    best = max(scores, key=lambda r: scores[r])
    return best if scores[best] > 0 else "researcher"


def _generate_name(role: str) -> str:
    """Generate a unique agent name based on role."""
    import random
    short_id = uuid.uuid4().hex[:4].upper()
    base = random.choice(_ROLE_NAMES.get(role, ["Agent"]))  # noqa: S311
    return f"{base}-{short_id}"


def _build_soul(role: str, name: str, task_context: dict) -> dict:
    """Build the SOUL configuration dict for an OpenClaw agent."""
    title = task_context.get("title", "")
    description = task_context.get("description", "") or ""
    tags = task_context.get("tags", [])
    priority = task_context.get("priority", "medium")

    skills = _ROLE_SKILLS.get(role, ["general_assistance"])
    personality_traits = _ROLE_PERSONALITY.get(role, ["helpful", "accurate"])

    system_prompt = f"""You are {name}, a specialized {role} agent operating within the OpenClaw Mission Control system.

## Current Assignment
Task: {title}
Priority: {priority}
{f'Context: {description}' if description else ''}
{f'Tags: {", ".join(tags)}' if tags else ''}

## Your Expertise
You are a highly capable {role} with deep expertise in: {", ".join(skills)}.

## Operating Principles
- Be {", ".join(personality_traits[:3])}
- Produce concrete, actionable outputs — not vague suggestions
- Think step by step before acting
- Report progress clearly and concisely
- Flag blockers or uncertainties immediately

## Communication Style
Use structured responses with clear sections. When completing subtasks, summarize findings before moving on.
Prioritize quality over speed, but maintain momentum.
"""

    return {
        "name": name,
        "role": role,
        "system_prompt": system_prompt,
        "personality": personality_traits,
        "skills": skills,
        "metadata": {
            "created_for_task": task_context.get("id"),
            "priority": priority,
            "tags": tags,
        },
    }


async def create_agent_for_task(task_context: dict, role: str | None = None) -> dict:
    """
    Full agent creation pipeline:
    1. Infer role from task context
    2. Build SOUL configuration
    3. Register on OpenClaw Gateway (if connected)
    4. Save to local DB
    5. Broadcast SSE event
    Returns the agent row dict.
    """
    if not role:
        role = _infer_role(task_context)

    name = _generate_name(role)
    soul = _build_soul(role, name, task_context)

    logger.info(f"Agent Factory: creating {role} agent '{name}' for task '{task_context.get('title', '')}'")

    # Register on gateway (non-fatal if not connected)
    gw_agent_id: str | None = None
    if gateway.connected:
        try:
            result = await gateway.create_agent(name=name, role=role, soul_config=soul)
            gw_agent_id = result.get("id") or result.get("agentId") or result.get("agent_id")
            logger.info(f"Agent Factory: registered on gateway as {gw_agent_id}")
        except Exception as e:
            logger.warning(f"Agent Factory: gateway registration failed (non-fatal): {e}")

    # Save to local DB
    agent_id = str(uuid.uuid4())
    db = await get_db()
    await db.execute(
        """INSERT INTO agents (id, gateway_agent_id, name, role, soul_config, status)
           VALUES (?, ?, ?, ?, ?, 'idle')""",
        (agent_id, gw_agent_id, name, role, json.dumps(soul)),
    )

    # Insert skills into agent_skills table
    for skill_name in soul["skills"]:
        await db.execute(
            """INSERT INTO agent_skills (id, agent_id, name, description, skill_source)
               VALUES (?, ?, ?, ?, 'soul')""",
            (str(uuid.uuid4()), agent_id, skill_name, f"{role} skill: {skill_name}", ),
        )

    await db.commit()

    # Fetch the inserted row
    async with db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)) as cursor:
        row = await cursor.fetchone()

    agent = dict(row)
    try:
        agent["soul_config"] = json.loads(agent.get("soul_config", "{}"))
    except (json.JSONDecodeError, TypeError):
        agent["soul_config"] = soul

    await sse.broadcast("agent.created", agent)
    logger.info(f"Agent Factory: agent {agent_id} created successfully")
    return agent
