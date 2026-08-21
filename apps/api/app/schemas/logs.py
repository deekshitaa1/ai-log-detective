from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LogEventCreate(BaseModel):
    timestamp: datetime
    level: str
    service: str
    message: str
    metadata_json: dict | None = None


class LogEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    timestamp: datetime
    level: str
    service: str
    message: str
    metadata_json: dict | None
