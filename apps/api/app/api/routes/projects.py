from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Project
from app.schemas.projects import ProjectCreate, ProjectResponse


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["projects"],
)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.slug == payload.slug)
    )

    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project slug already exists",
        )

    project = Project(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
    )

    db.add(project)

    await db.commit()
    await db.refresh(project)

    return project


@router.get(
    "",
    response_model=list[ProjectResponse],
)
async def list_projects(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project)
        .order_by(Project.created_at.desc())
    )

    return list(result.scalars().all())
