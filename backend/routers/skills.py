"""Skills Hub router — skill registry, agent bindings, and external registry integration."""
import json
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from database import get_db
from services.aegis import scan_content
from services.registry_client import search_registries, get_registry_stats, get_skill_from_registry, ALL_REGISTRIES
from models.phase4 import SkillCreate, SkillUpdate, SkillBindingCreate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skills", tags=["skills"])


def generate_skill_id() -> str:
    return f"skill-{uuid.uuid4().hex[:8]}"


def generate_binding_id() -> str:
    return f"bind-{uuid.uuid4().hex[:8]}"


@router.get("")
async def list_skills(category: str | None = None, skill_type: str | None = None):
    """List all skills in the registry."""
    db = await get_db()
    query = "SELECT * FROM skill_registry"
    params = []
    conditions = []
    if category:
        conditions.append("category = ?")
        params.append(category)
    if skill_type:
        conditions.append("skill_type = ?")
        params.append(skill_type)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY installed_at DESC"
    rows = await db.execute_fetchall(query, params)
    result = []
    for r in rows:
        d = dict(r)
        for f in ("input_schema", "output_schema", "tags"):
            if d.get(f):
                try:
                    d[f] = json.loads(d[f])
                except (json.JSONDecodeError, TypeError):
                    pass
        result.append(d)
    return result


@router.post("")
async def create_skill(body: SkillCreate):
    """Register a new skill in the hub."""
    db = await get_db()
    skill_id = generate_skill_id()

    # Security scan on prompt template
    audits = []
    if body.prompt_template:
        audits = await scan_content(body.prompt_template, "skill_prompt", skill_id)
        for audit in audits:
            if audit["severity"] == "critical":
                raise HTTPException(400, f"Security issue in prompt template: {audit['title']}")

    # Store any security findings
    for audit in audits:
        await db.execute(
            """INSERT INTO security_audits (id, audit_type, target_type, target_id, severity, title, description, recommendation, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (audit["id"], audit["audit_type"], "skill", skill_id, audit["severity"],
             audit["title"], audit["description"], audit["recommendation"],
             audit.get("metadata", "{}")),
        )

    await db.execute(
        """INSERT INTO skill_registry
        (id, name, description, category, skill_type, source_url, version, prompt_template, input_schema, output_schema, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (skill_id, body.name, body.description, body.category, body.skill_type,
         body.source_url, body.version, body.prompt_template,
         json.dumps(body.input_schema), json.dumps(body.output_schema), json.dumps(body.tags)),
    )
    await db.commit()
    return {"id": skill_id, "security_findings": len(audits)}


@router.get("/categories")
async def list_categories():
    """List distinct skill categories with counts."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT category, COUNT(*) as cnt FROM skill_registry GROUP BY category ORDER BY cnt DESC"
    )
    return [{"category": dict(r)["category"], "count": dict(r)["cnt"]} for r in rows]


@router.get("/stats")
async def skill_stats():
    """Get skill hub statistics."""
    db = await get_db()
    async with db.execute("SELECT COUNT(*) as cnt FROM skill_registry") as cur:
        row = await cur.fetchone()
    total_skills = dict(row)["cnt"]

    async with db.execute("SELECT COUNT(*) as cnt FROM agent_skill_bindings") as cur:
        row = await cur.fetchone()
    total_bindings = dict(row)["cnt"]

    type_rows = await db.execute_fetchall(
        "SELECT skill_type, COUNT(*) as cnt FROM skill_registry GROUP BY skill_type"
    )
    by_type = {dict(r)["skill_type"]: dict(r)["cnt"] for r in type_rows}

    top_rows = await db.execute_fetchall(
        "SELECT name, use_count FROM skill_registry ORDER BY use_count DESC LIMIT 5"
    )
    top_skills = [{"name": dict(r)["name"], "use_count": dict(r)["use_count"]} for r in top_rows]

    return {
        "total_skills": total_skills,
        "total_bindings": total_bindings,
        "by_type": by_type,
        "top_skills": top_skills,
    }


# ── External Registry Integration ─────────────────────────────────────────

@router.get("/registry/search")
async def search_external_registries(q: str = "", registry: str = "", category: str = ""):
    """Search across external skill registries (skills.sh, Skills Directory, Anthropic, Hugging Face)."""
    results = search_registries(query=q, registry=registry, category=category)
    return {"query": q, "total": len(results), "results": results}


@router.get("/registry/stats")
async def registry_stats():
    """Get stats for each external registry."""
    return {"registries": get_registry_stats()}


@router.get("/registry/list")
async def list_registry_skills(registry: str = ""):
    """List all skills from a specific registry or all registries."""
    registries = [registry] if registry and registry in ALL_REGISTRIES else list(ALL_REGISTRIES.keys())
    results = []
    for reg_name in registries:
        for skill in ALL_REGISTRIES.get(reg_name, []):
            results.append(skill.to_dict())
    results.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    return {"total": len(results), "results": results}


class RegistryInstallRequest:
    """Request body for installing a skill from an external registry."""
    def __init__(self, name: str, registry: str, category: str = "general"):
        self.name = name
        self.registry = registry
        self.category = category


from pydantic import BaseModel

class RegistryInstallBody(BaseModel):
    name: str
    registry: str
    category: str = "general"


@router.post("/registry/install")
async def install_from_registry(body: RegistryInstallBody):
    """Install a skill from an external registry into the local Skills Hub."""
    skill = get_skill_from_registry(body.name, body.registry)
    if not skill:
        raise HTTPException(404, f"Skill '{body.name}' not found in registry '{body.registry}'")

    db = await get_db()

    # Check if already installed
    existing = await db.execute_fetchall(
        "SELECT id FROM skill_registry WHERE name = ? AND source_url = ?",
        (skill.name, skill.source_url),
    )
    if existing:
        return {"status": "already_installed", "id": dict(existing[0])["id"]}

    # Security scan on prompt template
    audits = []
    if skill.description:
        audits = await scan_content(skill.description, "skill_description", skill.name)

    skill_id = generate_skill_id()

    await db.execute(
        """INSERT INTO skill_registry
        (id, name, description, category, skill_type, source_url, version, prompt_template, input_schema, output_schema, tags, trust_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (skill_id, skill.name, skill.description, body.category or skill.category,
         skill.skill_type, skill.source_url, skill.version,
         "", "{}", "{}", json.dumps(skill.tags), skill.popularity / 1000.0),  # Rough trust from popularity
    )

    # Store any security findings
    for audit in audits:
        await db.execute(
            """INSERT INTO security_audits
            (id, audit_type, target_type, target_id, severity, title, description, recommendation, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (audit["id"], audit["audit_type"], "skill", skill_id, audit["severity"],
             audit["title"], audit["description"], audit["recommendation"],
             audit.get("metadata", "{}")),
        )

    await db.commit()
    return {
        "status": "installed",
        "id": skill_id,
        "name": skill.name,
        "registry": body.registry,
        "install_command": skill.install_command,
        "security_findings": len(audits),
    }


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    """Get a skill's full details."""
    db = await get_db()
    async with db.execute("SELECT * FROM skill_registry WHERE id = ?", (skill_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Skill not found")
    d = dict(row)
    for f in ("input_schema", "output_schema", "tags"):
        if d.get(f):
            try:
                d[f] = json.loads(d[f])
            except (json.JSONDecodeError, TypeError):
                pass
    # Get bound agents
    bindings = await db.execute_fetchall(
        """SELECT ab.*, a.name as agent_name
        FROM agent_skill_bindings ab
        LEFT JOIN agents a ON a.id = ab.agent_id
        WHERE ab.skill_id = ?""",
        (skill_id,),
    )
    d["bindings"] = [dict(b) for b in bindings]
    return d


@router.put("/{skill_id}")
async def update_skill(skill_id: str, body: SkillUpdate):
    """Update a skill's metadata."""
    db = await get_db()
    updates = []
    params = []
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "tags" and value is not None:
            updates.append(f"{field} = ?")
            params.append(json.dumps(value))
        else:
            updates.append(f"{field} = ?")
            params.append(value)
    if not updates:
        return {"updated": False}
    updates.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(skill_id)
    await db.execute(f"UPDATE skill_registry SET {', '.join(updates)} WHERE id = ?", params)
    await db.commit()
    return {"updated": True}


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    """Remove a skill from the registry."""
    db = await get_db()
    await db.execute("DELETE FROM agent_skill_bindings WHERE skill_id = ?", (skill_id,))
    await db.execute("DELETE FROM skill_registry WHERE id = ?", (skill_id,))
    await db.commit()
    return {"deleted": True}


# ── Agent-Skill Bindings ───────────────────────────────────────────────────

@router.post("/bind")
async def bind_skill_to_agent(body: SkillBindingCreate):
    """Bind a skill to an agent."""
    db = await get_db()
    binding_id = generate_binding_id()
    try:
        await db.execute(
            """INSERT INTO agent_skill_bindings (id, agent_id, skill_id, confidence_score, custom_config)
            VALUES (?, ?, ?, ?, ?)""",
            (binding_id, body.agent_id, body.skill_id, body.confidence_score, json.dumps(body.custom_config)),
        )
        await db.commit()
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(409, "Skill already bound to this agent")
        raise
    return {"id": binding_id, "status": "bound"}


@router.delete("/unbind/{agent_id}/{skill_id}")
async def unbind_skill(agent_id: str, skill_id: str):
    """Remove a skill binding from an agent."""
    db = await get_db()
    await db.execute(
        "DELETE FROM agent_skill_bindings WHERE agent_id = ? AND skill_id = ?",
        (agent_id, skill_id),
    )
    await db.commit()
    return {"unbound": True}


@router.get("/agent/{agent_id}")
async def get_agent_skills(agent_id: str):
    """Get all skills bound to an agent."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT ab.*, sr.name as skill_name, sr.description, sr.category, sr.skill_type,
        sr.prompt_template, sr.use_count, sr.success_count, sr.trust_score
        FROM agent_skill_bindings ab
        JOIN skill_registry sr ON sr.id = ab.skill_id
        WHERE ab.agent_id = ?""",
        (agent_id,),
    )
    result = []
    for r in rows:
        d = dict(r)
        if d.get("custom_config"):
            try:
                d["custom_config"] = json.loads(d["custom_config"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result
