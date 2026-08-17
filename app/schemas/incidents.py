from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IncidentCreate(BaseModel):
    project_id: UUID
    title: str = Field(min_length=3, max_length=300)
    description: str | None = None
    severity: str = Field(default="medium", max_length=30)


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: str
    severity: str
    started_at: datetime
    resolved_at: datetime | None
    created_at: datetime
