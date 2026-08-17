from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Incident, Project, LogEvent, Detection
from app.schemas.incidents import IncidentCreate, IncidentResponse

from app.services.detection import detect_log_event
from app.services.correlation import correlate_detections
from app.services.rca import analyze_root_cause
from app.services.code_localization import localize_code
from app.services.repair import propose_repair


router = APIRouter(
    prefix="/api/v1/incidents",
    tags=["incidents"],
)


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    payload: IncidentCreate,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, payload.project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    incident = Incident(
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
    )

    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    return incident


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
)
async def get_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return incident


@router.get(
    "",
    response_model=list[IncidentResponse],
)
async def list_incidents(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Incident)
        .order_by(Incident.created_at.desc())
        .limit(100)
    )

    return list(result.scalars().all())


@router.post(
    "/{incident_id}/analyze",
)
async def analyze_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    logs_result = await db.execute(
        select(LogEvent)
        .where(LogEvent.incident_id == incident_id)
        .order_by(LogEvent.timestamp.asc())
    )

    logs = list(logs_result.scalars().all())

    if not logs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No logs found for this incident",
        )

    all_detections = []

    for log in logs:
        signals = detect_log_event(log)

        for signal in signals:
            detection = Detection(
                id=uuid4(),
                incident_id=incident_id,
                detector=signal.detector,
                signal=signal.signal,
                confidence=signal.confidence,
                evidence=signal.evidence,
            )

            db.add(detection)
            all_detections.append(detection)

    await db.flush()

    if not all_detections:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No detection signals were produced",
        )

    correlation = correlate_detections(all_detections)

    rca = analyze_root_cause(correlation)

    project = await db.get(Project, incident.project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    repository = getattr(project, "repository", None)

    location = await localize_code(
        rca,
        repository,
    )

    repair = propose_repair(
        rca,
        location,
    )

    await db.commit()

    return {
        "incident_id": str(incident.id),
        "detection": [
            {
                "detector": d.detector,
                "signal": d.signal,
                "confidence": d.confidence,
            }
            for d in all_detections
        ],
        "correlation": {
            "failure_domain": correlation.failure_domain,
            "primary_service": correlation.primary_service,
            "dependency": correlation.suspected_dependency,
            "failure_pattern": correlation.failure_pattern,
            "confidence": correlation.confidence,
        },
        "rca": {
            "root_cause": rca.root_cause,
            "affected_service": rca.affected_service,
            "affected_dependency": rca.affected_dependency,
            "confidence": rca.confidence,
            "explanation": rca.explanation,
        },
        "localization": {
            "repository": location.repository,
            "file_path": location.file_path,
            "symbol": location.symbol,
            "line_start": location.line_start,
            "line_end": location.line_end,
            "confidence": location.confidence,
            "reasoning": location.reasoning,
            "evidence": location.evidence,
        },
        "repair": {
            "title": repair.title,
            "summary": repair.summary,
            "proposed_change": repair.proposed_change,
            "confidence": repair.confidence,
            "risk": repair.risk,
            "validation_steps": repair.validation_steps,
        },
    }
