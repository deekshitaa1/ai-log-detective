from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LogEventCreate(BaseModel):
    timestamp: datetime
    level: str = Field(min_length=1, max_length=20)
    service: str = Field(min_length=1, max_length=150)
    message: str = Field(min_length=1)
    metadata_json: dict = Field(default_factory=dict)


class LogEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    timestamp: datetime
    level: str
    service: str
    message: str
    metadata_json: dict
