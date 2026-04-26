from pydantic import BaseModel
from typing import Optional


class AgentCreate(BaseModel):
    name: str
    role: str = ""
    soul_config: dict = {}
    gateway_agent_id: Optional[str] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    soul_config: Optional[dict] = None
    status: Optional[str] = None


class Agent(BaseModel):
    id: str
    gateway_agent_id: Optional[str]
    name: str
    role: str
    soul_config: dict = {}
    status: str
    trust_score: float
    parent_orchestrator_id: Optional[str]
    created_at: str
    updated_at: str
