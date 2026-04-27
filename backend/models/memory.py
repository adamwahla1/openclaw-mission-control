"""Memory model definitions."""

from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "fact"  # fact | insight | procedure | experience | preference
    category: str = "general"
    source: str = ""
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    connections: list[str] = Field(default_factory=list)  # IDs of connected memories


class MemoryUpdate(BaseModel):
    content: str | None = None
    memory_type: str | None = None
    category: str | None = None
    importance: float | None = None
    decay_score: float | None = None
    tags: list[str] | None = None


class ConnectionCreate(BaseModel):
    target_memory_id: str
    connection_type: str = "related"  # related | causes | contradicts | supports | derives
    strength: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryExtractRequest(BaseModel):
    """Request to extract memories from text (e.g., a task report or debate)."""
    source_text: str
    source_type: str = "report"  # report | debate | conversation | document
    agent_id: str | None = None
