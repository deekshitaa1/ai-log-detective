from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Incident, LogEvent
from app.schemas.logs import LogEventCreate, LogEventResponse


router = APIRouter(
    prefix="/api/v1/incidents/{incident_id}/logs",
    tags=["logs"],
)


@router.post(
    "",
    response_model=LogEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_log(
    incident_id: UUID,
    payload: LogEventCreate,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    log = LogEvent(
        incident_id=incident_id,
        timestamp=payload.timestamp,
        level=payload.level,
        service=payload.service,
        message=payload.message,
        metadata_json=payload.metadata_json,
    )

    db.add(log)

    await db.commit()
    await db.refresh(log)

    return log


@router.get(
    "",
    response_model=list[LogEventResponse],
)
async def list_logs(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    result = await db.execute(
        select(LogEvent)
        .where(LogEvent.incident_id == incident_id)
        .order_by(LogEvent.timestamp.asc())
    )

    return list(result.scalars().all())
