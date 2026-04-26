from pydantic import BaseModel
from typing import Optional


class DebateCreate(BaseModel):
    topic: str
    max_rounds: int = 5


class DebateMessageCreate(BaseModel):
    agent_id: str
    content: str
    stance: Optional[str] = None
    response_to_id: Optional[str] = None


class DebateQuestionCreate(BaseModel):
    question: str
    asked_by_agent_id: Optional[str] = None
