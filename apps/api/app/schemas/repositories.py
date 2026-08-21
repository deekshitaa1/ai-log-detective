from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    provider: str
    owner: str
    name: str
    default_branch: str


class RepositoryFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    path: str
    language: str | None
    size_bytes: int
    sha: str | None


class RepositoryIngestionResponse(BaseModel):
    repository_id: UUID
    commit_sha: str
    files_ingested: int
    files_skipped: int
    total_bytes: int
