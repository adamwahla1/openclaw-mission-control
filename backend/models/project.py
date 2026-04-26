from pydantic import BaseModel
from typing import Optional


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectFileCreate(BaseModel):
    filename: str
    filepath: str
    task_id: Optional[str] = None
    file_type: Optional[str] = None
    pinned: Optional[bool] = None


class HandoverCreate(BaseModel):
    content_md: str
    task_id: Optional[str] = None
    summary: Optional[str] = None
    key_decisions: Optional[list[str]] = None
    open_questions: Optional[list[str]] = None
