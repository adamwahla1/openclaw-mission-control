"""Security Audit router — trust scoring, secret detection, audit log."""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from database import get_db
from services.aegis import audit_agent_behavior, scan_content, calculate_trust_score
from models.phase4 import SecurityScanRequest, AuditResolve

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/audits")
async def list_audits(
    severity: str | None = None,
    status: str | None = None,
    target_type: str | None = None,
    limit: int = 100,
):
    """List security audit findings."""
    db = await get_db()
    query = "SELECT * FROM security_audits"
    params = []
    conditions = []
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if target_type:
        conditions.append("target_type = ?")
        params.append(target_type)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY detected_at DESC LIMIT ?"
    params.append(limit)
    rows = await db.execute_fetchall(query, params)
    result = []
    for r in rows:
        d = dict(r)
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result


@router.get("/stats")
async def security_stats():
    """Get security audit summary statistics."""
    db = await get_db()

    async with db.execute("SELECT COUNT(*) as cnt FROM security_audits WHERE status = 'open'") as cur:
        row = await cur.fetchone()
    open_count = dict(row)["cnt"]

    async with db.execute("SELECT COUNT(*) as cnt FROM security_audits") as cur:
        row = await cur.fetchone()
    total_count = dict(row)["cnt"]

    sev_rows = await db.execute_fetchall(
        "SELECT severity, COUNT(*) as cnt FROM security_audits WHERE status = 'open' GROUP BY severity"
    )
    by_severity = {dict(r)["severity"]: dict(r)["cnt"] for r in sev_rows}

    type_rows = await db.execute_fetchall(
        "SELECT audit_type, COUNT(*) as cnt FROM security_audits WHERE status = 'open' GROUP BY audit_type"
    )
    by_type = {dict(r)["audit_type"]: dict(r)["cnt"] for r in type_rows}

    return {
        "open_count": open_count,
        "total_count": total_count,
        "resolved_count": total_count - open_count,
        "by_severity": by_severity,
        "by_type": by_type,
    }


@router.post("/scan")
async def scan_content_endpoint(body: SecurityScanRequest):
    """Scan content for secrets and risky patterns."""
    findings = await scan_content(body.content, body.content_type, body.content_id)

    # Store findings
    db = await get_db()
    for finding in findings:
        await db.execute(
            """INSERT INTO security_audits
            (id, audit_type, target_type, target_id, severity, title, description, recommendation, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (finding["id"], finding["audit_type"], finding["target_type"], finding["target_id"],
             finding["severity"], finding["title"], finding["description"], finding["recommendation"],
             finding.get("metadata", "{}")),
        )
    await db.commit()
    return {"findings": findings, "total": len(findings)}


@router.post("/audit-agent/{agent_id}")
async def audit_agent(agent_id: str):
    """Run a full security audit on an agent."""
    db = await get_db()

    # Fetch agent data
    async with db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Agent not found")
    agent = dict(row)

    # Get agent skills
    skill_rows = await db.execute_fetchall(
        """SELECT sr.* FROM skill_registry sr
        JOIN agent_skill_bindings ab ON ab.skill_id = sr.id
        WHERE ab.agent_id = ?""",
        (agent_id,),
    )
    skills = [dict(s) for s in skill_rows]
    for s in skills:
        for f in ("input_schema", "output_schema", "tags"):
            if s.get(f):
                try:
                    s[f] = json.loads(s[f])
                except (json.JSONDecodeError, TypeError):
                    pass
    agent["skills"] = skills

    # Count open audits
    async with db.execute(
        "SELECT COUNT(*) as cnt FROM security_audits WHERE target_id = ? AND status = 'open'",
        (agent_id,),
    ) as cur:
        row = await cur.fetchone()
    agent["open_audit_count"] = dict(row)["cnt"]

    # Run audit
    audits = await audit_agent_behavior(agent_id, agent)

    # Store results
    for audit in audits:
        await db.execute(
            """INSERT INTO security_audits
            (id, audit_type, target_type, target_id, severity, title, description, recommendation, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (audit["id"], audit["audit_type"], audit["target_type"], audit["target_id"],
             audit["severity"], audit["title"], audit["description"], audit["recommendation"],
             audit.get("metadata", "{}")),
        )

    # Update trust score
    trust_score = calculate_trust_score(agent)
    await db.execute(
        "UPDATE agents SET trust_score = ?, updated_at = ? WHERE id = ?",
        (trust_score, datetime.utcnow().isoformat(), agent_id),
    )

    await db.commit()
    return {
        "agent_id": agent_id,
        "trust_score": trust_score,
        "audits_found": len(audits),
        "audits": audits,
    }


@router.get("/trust/{agent_id}")
async def get_trust_score(agent_id: str):
    """Get an agent's current trust score."""
    db = await get_db()
    async with db.execute("SELECT trust_score, name FROM agents WHERE id = ?", (agent_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Agent not found")
    d = dict(row)
    return {"agent_id": agent_id, "name": d["name"], "trust_score": d["trust_score"]}


@router.put("/resolve/{audit_id}")
async def resolve_audit(audit_id: str, body: AuditResolve):
    """Resolve a security audit finding."""
    db = await get_db()
    now = datetime.utcnow().isoformat()
    result = await db.execute(
        "UPDATE security_audits SET status = 'resolved', resolved_by = ?, resolved_at = ? WHERE id = ?",
        (body.resolved_by, now, audit_id),
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(404, "Audit not found")
    return {"resolved": True, "resolved_at": now}
