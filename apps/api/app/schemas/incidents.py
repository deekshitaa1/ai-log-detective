from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IncidentCreate(BaseModel):
    project_id: UUID
    title: str
    description: str
    severity: str = "medium"
    started_at: datetime | None = None


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    description: str
    status: str
    severity: str
    started_at: datetime
    resolved_at: datetime | None
    created_at: datetime
