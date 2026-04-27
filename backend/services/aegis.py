"""Aegis — Security & quality guard service."""
import uuid
import json
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Secret patterns for detection
SECRET_PATTERNS = [
    (r'(?:api[_-]?key|apikey)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})["\']?', "API Key"),
    (r'(?:secret|token|password|passwd)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{16,})["\']?', "Secret/Token"),
    (r'(?:AKIA|ABIA|ACCA|AGPA|AIDA|AIPA|ANPA|ANVA|APKA|AROA|ASCA|ASIA)[0-9A-Z]{16}', "AWS Access Key"),
    (r'ghp_[A-Za-z0-9_]{36}', "GitHub Personal Access Token"),
    (r'gho_[A-Za-z0-9_]{36}', "GitHub OAuth Token"),
    (r'glpat-[A-Za-z0-9\-]{20}', "GitLab Personal Access Token"),
    (r'sk-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}', "OpenAI API Key"),
    (r'AIza[A-Za-z0-9_\\-]{35}', "Google API Key"),
    (r'(?:-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----)', "Private Key"),
    (r'mongodb(?:\+srv)?://[^\s]+', "MongoDB Connection String"),
    (r'postgresql?://[^\s]+', "PostgreSQL Connection String"),
    (r'mysql://[^\s]+', "MySQL Connection String"),
    (r'redis://[^\s]+', "Redis Connection String"),
]

# Risk patterns for agent behavior
RISK_PATTERNS = [
    ("exec\\(|os\\.system\\(|subprocess\\.", "Command Execution", "critical"),
    ("eval\\(|__import__\\(", "Dynamic Code Execution", "critical"),
    ("requests\\.get\\(|requests\\.post\\(|urllib", "External HTTP Request", "warning"),
    ("open\\(|read\\(|write\\(", "File System Access", "warning"),
    ("DROP TABLE|DELETE FROM|TRUNCATE", "Destructive SQL", "critical"),
    ("rm -rf|del /s|format ", "Destructive File Operation", "critical"),
    ("sudo |chmod 777", "Privilege Escalation", "critical"),
]


def generate_audit_id() -> str:
    return f"aud-{uuid.uuid4().hex[:8]}"


def scan_for_secrets(content: str) -> list[dict]:
    """Scan content for leaked secrets. Returns list of findings."""
    findings = []
    for pattern, secret_type in SECRET_PATTERNS:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            # Mask the actual value
            full_match = match.group(0)
            masked = full_match[:10] + "..." + full_match[-4:] if len(full_match) > 14 else full_match[:5] + "***"
            findings.append({
                "type": secret_type,
                "pattern": masked,
                "position": match.start(),
                "severity": "critical",
                "recommendation": f"Rotate the exposed {secret_type} immediately and move to environment variables or secrets manager."
            })
    return findings


def scan_for_risks(content: str) -> list[dict]:
    """Scan content for risky patterns. Returns list of findings."""
    findings = []
    for pattern, risk_name, severity in RISK_PATTERNS:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            findings.append({
                "type": risk_name,
                "pattern": match.group(0),
                "position": match.start(),
                "severity": severity,
                "recommendation": f"Review this {risk_name} usage for safety."
            })
    return findings


def calculate_trust_score(agent_data: dict) -> float:
    """Calculate an agent's trust score based on multiple factors."""
    base_score = 50.0

    # Success rate factor
    success_count = agent_data.get("success_count", 0)
    total_count = agent_data.get("use_count", 1)
    if total_count > 0:
        success_rate = success_count / total_count
        base_score += success_rate * 30  # Up to +30

    # Skill confidence factor
    skills = agent_data.get("skills", [])
    if skills:
        avg_confidence = sum(s.get("confidence_score", 0.5) for s in skills) / len(skills)
        base_score += avg_confidence * 15  # Up to +15

    # Security audit factor
    open_audits = agent_data.get("open_audit_count", 0)
    base_score -= open_audits * 5  # -5 per open audit

    # Uptime factor
    error_count = agent_data.get("error_count", 0)
    base_score -= min(error_count * 2, 10)  # -2 per error, max -10

    return max(0.0, min(100.0, base_score))


async def audit_agent_behavior(agent_id: str, agent_data: dict) -> list[dict]:
    """Perform a security audit on an agent's recent behavior."""
    audits = []

    # Check SOUL config for risky patterns
    soul_config = agent_data.get("soul_config", {})
    if isinstance(soul_config, str):
        try:
            soul_config = json.loads(soul_config)
        except json.JSONDecodeError:
            soul_config = {}

    soul_str = json.dumps(soul_config)
    secret_findings = scan_for_secrets(soul_str)
    for finding in secret_findings:
        audits.append({
            "id": generate_audit_id(),
            "audit_type": "secret_detection",
            "target_type": "agent",
            "target_id": agent_id,
            "severity": finding["severity"],
            "title": f"Secret detected in agent config: {finding['type']}",
            "description": f"A {finding['type']} pattern was found in the agent's SOUL configuration.",
            "recommendation": finding["recommendation"],
            "status": "open",
            "metadata": json.dumps({"pattern_type": finding["type"], "position": finding["position"]}),
        })

    # Check skill prompts for risky patterns
    skills = agent_data.get("skills", [])
    for skill in skills:
        prompt = skill.get("prompt_template", "")
        risk_findings = scan_for_risks(prompt)
        for finding in risk_findings:
            audits.append({
                "id": generate_audit_id(),
                "audit_type": "risk_pattern",
                "target_type": "agent_skill",
                "target_id": f"{agent_id}:{skill.get('name', 'unknown')}",
                "severity": finding["severity"],
                "title": f"Risky pattern in skill: {finding['type']}",
                "description": f"A {finding['type']} pattern was found in skill prompt template.",
                "recommendation": finding["recommendation"],
                "status": "open",
                "metadata": json.dumps({"pattern_type": finding["type"], "pattern": finding["pattern"]}),
            })

    # Trust score evaluation
    trust = calculate_trust_score(agent_data)
    if trust < 30:
        audits.append({
            "id": generate_audit_id(),
            "audit_type": "trust_score",
            "target_type": "agent",
            "target_id": agent_id,
            "severity": "warning",
            "title": f"Low trust score: {trust:.1f}",
            "description": f"Agent trust score is {trust:.1f}/100, which is below the safety threshold.",
            "recommendation": "Review agent behavior and recent audit findings before granting elevated permissions.",
            "status": "open",
            "metadata": json.dumps({"trust_score": trust}),
        })

    return audits


async def scan_content(content: str, content_type: str = "general", content_id: str = "") -> list[dict]:
    """Scan arbitrary content for security issues."""
    audits = []

    # Secret scan
    secret_findings = scan_for_secrets(content)
    for finding in secret_findings:
        audits.append({
            "id": generate_audit_id(),
            "audit_type": "secret_detection",
            "target_type": content_type,
            "target_id": content_id,
            "severity": finding["severity"],
            "title": f"Secret detected: {finding['type']}",
            "description": f"A {finding['type']} was found in {content_type} content.",
            "recommendation": finding["recommendation"],
            "status": "open",
            "metadata": json.dumps({"position": finding["position"]}),
        })

    # Risk scan
    risk_findings = scan_for_risks(content)
    for finding in risk_findings:
        audits.append({
            "id": generate_audit_id(),
            "audit_type": "risk_pattern",
            "target_type": content_type,
            "target_id": content_id,
            "severity": finding["severity"],
            "title": f"Risky pattern: {finding['type']}",
            "description": f"A {finding['type']} pattern was found in {content_type} content.",
            "recommendation": finding["recommendation"],
            "status": "open",
            "metadata": json.dumps({"pattern": finding["pattern"]}),
        })

    return audits
