from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    board_id: Optional[str] = None
    project_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    tags: list[str] = []


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    board_id: Optional[str] = None
    project_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    tags: Optional[list[str]] = None


class Task(BaseModel):
    id: str
    title: str
    description: str
    status: str
    priority: str
    board_id: Optional[str]
    project_id: Optional[str]
    assigned_agent_id: Optional[str]
    parent_task_id: Optional[str]
    gateway_session_id: Optional[str]
    tags: list[str] = []
    is_template: bool = False
    created_at: str
    updated_at: str


class TaskComment(BaseModel):
    id: str
    task_id: str
    author_type: str
    author_id: Optional[str]
    content: str
    created_at: str
