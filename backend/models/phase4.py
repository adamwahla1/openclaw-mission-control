"""Pydantic models for Phase 4 — Autopilot, Skills, Security, Costs."""
from pydantic import BaseModel


# ── Autopilot ──────────────────────────────────────────────────────────────

class AutopilotRunCreate(BaseModel):
    name: str = "Autopilot Run"
    objective: str
    template: str = "feature"
    approval_required: bool = True
    pipeline_config: dict = {}

class AutopilotRunUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    approval_required: bool | None = None

class AutopilotApproval(BaseModel):
    approved_by: str


# ── Skills ─────────────────────────────────────────────────────────────────

class SkillCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    skill_type: str = "internal"
    source_url: str = ""
    version: str = "1.0.0"
    prompt_template: str = ""
    input_schema: dict = {}
    output_schema: dict = {}
    tags: list[str] = []

class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    prompt_template: str | None = None
    tags: list[str] | None = None

class SkillBindingCreate(BaseModel):
    agent_id: str
    skill_id: str
    confidence_score: float = 0.5
    custom_config: dict = {}


# ── Security ───────────────────────────────────────────────────────────────

class SecurityScanRequest(BaseModel):
    content: str
    content_type: str = "general"
    content_id: str = ""

class AuditResolve(BaseModel):
    resolved_by: str


# ── Costs ──────────────────────────────────────────────────────────────────

class CostRecordCreate(BaseModel):
    agent_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    model: str = ""
    operation: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

class CostSummaryRequest(BaseModel):
    group_by: str = "agent"
    days: int = 30


# ── Webhooks ───────────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    name: str
    url: str
    event_types: list[str] = []
    secret: str = ""

class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    event_types: list[str] | None = None
    is_active: bool | None = None


# ── Recurring Tasks ────────────────────────────────────────────────────────

class RecurringTaskCreate(BaseModel):
    name: str
    task_template_id: str | None = None
    cron_expression: str
    next_run_at: str

class RecurringTaskUpdate(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    next_run_at: str | None = None
    is_active: bool | None = None
