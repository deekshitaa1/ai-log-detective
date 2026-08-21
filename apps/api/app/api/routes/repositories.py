from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Repository, RepositoryFile
from app.schemas.repositories import (
    RepositoryFileResponse,
    RepositoryIngestionResponse,
    RepositoryResponse,
)
from app.services.github_ingestion import (
    GitHubIngestionError,
    fetch_repository_files,
)


router = APIRouter(
    prefix="/api/v1/repositories",
    tags=["repositories"],
)


@router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
)
async def get_repository(
    repository_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    repository = await db.get(
        Repository,
        repository_id,
    )

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    return repository


@router.post(
    "/{repository_id}/ingest",
    response_model=RepositoryIngestionResponse,
)
async def ingest_repository(
    repository_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    repository = await db.get(
        Repository,
        repository_id,
    )

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    if repository.provider.lower() != "github":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Repository ingestion currently supports "
                "GitHub repositories only"
            ),
        )

    try:
        commit_sha, files = await fetch_repository_files(
            owner=repository.owner,
            repository=repository.name,
            branch=repository.default_branch,
        )
    except GitHubIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    await db.execute(
        delete(RepositoryFile).where(
            RepositoryFile.repository_id == repository.id
        )
    )

    total_bytes = 0

    for file in files:
        db.add(
            RepositoryFile(
                repository_id=repository.id,
                path=file.path,
                language=file.language,
                size_bytes=file.size_bytes,
                sha=file.sha,
                content=file.content,
            )
        )

        total_bytes += file.size_bytes

    await db.commit()

    return RepositoryIngestionResponse(
        repository_id=repository.id,
        commit_sha=commit_sha,
        files_ingested=len(files),
        files_skipped=0,
        total_bytes=total_bytes,
    )


@router.get(
    "/{repository_id}/files",
    response_model=list[RepositoryFileResponse],
)
async def list_repository_files(
    repository_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    repository = await db.get(
        Repository,
        repository_id,
    )

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    result = await db.execute(
        select(RepositoryFile)
        .where(
            RepositoryFile.repository_id == repository_id
        )
        .order_by(RepositoryFile.path.asc())
    )

    return list(result.scalars().all())
