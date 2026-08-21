from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import (
    Detection,
    Incident,
    LogEvent,
    Project,
    RepairCandidate,
    Repository,
    RepositoryFile,
)
from app.schemas.incidents import IncidentCreate, IncidentResponse
from app.services.correlation import correlate_detections
from app.services.detection import detect_log_event
from app.services.evidence import aggregate_incident_evidence
from app.services.localization import localize_detections
from app.services.rca import analyze_root_cause
from app.services.repair import generate_repair_proposal
from app.services.repair_validation import validate_repair_candidate
from app.services.repair_verification import verify_repair
from app.services.github_remediation import (
    GitHubRemediationError,
    create_repair_pull_request,
    get_pull_request_status,
)


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

    started_at = payload.started_at or datetime.now(timezone.utc)

    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    incident = Incident(
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        started_at=started_at,
    )

    db.add(incident)

    await db.commit()
    await db.refresh(incident)

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


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
)
async def get_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(
        Incident,
        incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return incident


@router.post(
    "/{incident_id}/detect",
)
async def detect_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(
        Incident,
        incident_id,
    )

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

    logs = list(result.scalars().all())

    if not logs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No logs found for this incident",
        )

    detections = []

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
            detections.append(detection)

    if not detections:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No detection signals were produced",
        )

    await db.commit()

    return {
        "incident_id": str(incident.id),
        "detections": [
            {
                "id": str(detection.id),
                "detector": detection.detector,
                "signal": detection.signal,
                "confidence": detection.confidence,
                "evidence": detection.evidence,
            }
            for detection in detections
        ],
    }


@router.post(
    "/{incident_id}/correlate",
)
async def correlate_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(
        Incident,
        incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    result = await db.execute(
        select(Detection)
        .where(Detection.incident_id == incident_id)
        .order_by(Detection.id.asc())
    )

    detections = list(result.scalars().all())

    if not detections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No detections found for this incident",
        )

    correlation = correlate_detections(detections)

    return {
        "incident_id": str(incident.id),
        "correlation": {
            "failure_domain": correlation.failure_domain,
            "primary_service": correlation.primary_service,
            "dependency": correlation.suspected_dependency,
            "failure_pattern": correlation.failure_pattern,
            "confidence": correlation.confidence,
        },
        "source_detections": [
            {
                "id": str(detection.id),
                "detector": detection.detector,
                "confidence": detection.confidence,
            }
            for detection in detections
        ],
    }


@router.post(
    "/{incident_id}/rca",
)
async def root_cause_analysis(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(
        Incident,
        incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    result = await db.execute(
        select(Detection)
        .where(Detection.incident_id == incident_id)
        .order_by(Detection.id.asc())
    )

    detections = list(result.scalars().all())

    if not detections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No detections found for this incident",
        )

    correlation = correlate_detections(detections)

    investigation = aggregate_incident_evidence(
        incident=incident,
        detections=detections,
        correlation=correlation,
    )

    rca = analyze_root_cause(
        incident=incident,
        correlation=correlation,
        detections=detections,
        investigation=investigation,
    )

    return {
        "incident_id": str(incident.id),
        "correlation": {
            "failure_domain": correlation.failure_domain,
            "primary_service": correlation.primary_service,
            "dependency": correlation.suspected_dependency,
            "failure_pattern": correlation.failure_pattern,
            "confidence": correlation.confidence,
        },
        "root_cause_analysis": {
            "root_cause": rca.root_cause,
            "explanation": rca.explanation,
            "confidence": rca.confidence,
            "affected_service": rca.affected_service,
            "dependency": rca.dependency,
            "impact": rca.impact,
            "evidence": rca.evidence,
            "recommended_checks": rca.recommended_checks,
        },
    }


@router.post(
    "/{incident_id}/localize",
)
async def localize_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(
        Incident,
        incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    repository_result = await db.execute(
        select(Repository)
        .where(
            Repository.project_id == incident.project_id
        )
        .order_by(Repository.created_at.asc())
    )

    repository = repository_result.scalars().first()

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No repository configured for this project",
        )

    files_result = await db.execute(
        select(RepositoryFile)
        .where(
            RepositoryFile.repository_id == repository.id
        )
    )

    files = list(files_result.scalars().all())

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Repository has no ingested files. "
                "Run repository ingestion first."
            ),
        )

    detection_result = await db.execute(
        select(Detection)
        .where(
            Detection.incident_id == incident_id
        )
        .order_by(Detection.id.asc())
    )

    detections = list(
        detection_result.scalars().all()
    )

    if not detections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No detections found for this incident. "
                "Run detection first."
            ),
        )

    results = localize_detections(
        detections=detections,
        files=files,
    )

    return {
        "incident_id": str(incident.id),
        "repository_id": str(repository.id),
        "repository": {
            "owner": repository.owner,
            "name": repository.name,
            "branch": repository.default_branch,
        },
        "matches": [
            {
                "file_id": result.file_id,
                "path": result.path,
                "language": result.language,
                "confidence": result.confidence,
                "matched_signals": result.matched_signals,
                "evidence": result.evidence,
            }
            for result in results
        ],
        "total_matches": len(results),
    }


@router.post(
    "/{incident_id}/repair",
)
async def generate_incident_repair(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(
        Incident,
        incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    repository_result = await db.execute(
        select(Repository)
        .where(
            Repository.project_id == incident.project_id
        )
        .order_by(Repository.created_at.asc())
    )

    repository = repository_result.scalars().first()

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No repository configured for this project",
        )

    files_result = await db.execute(
        select(RepositoryFile)
        .where(
            RepositoryFile.repository_id == repository.id
        )
    )

    files = list(files_result.scalars().all())

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Repository has no ingested files. "
                "Run repository ingestion first."
            ),
        )

    detection_result = await db.execute(
        select(Detection)
        .where(
            Detection.incident_id == incident_id
        )
        .order_by(Detection.id.asc())
    )

    detections = list(
        detection_result.scalars().all()
    )

    if not detections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No detections found for this incident. "
                "Run detection first."
            ),
        )

    localization_results = localize_detections(
        detections=detections,
        files=files,
    )

    if not localization_results:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No repository files could be localized "
                "for this incident"
            ),
        )

    localization_results = sorted(
        localization_results,
        key=lambda item: item.confidence,
        reverse=True,
    )

    selected_match = localization_results[0]

    repository_file = await db.get(
        RepositoryFile,
        UUID(selected_match.file_id),
    )

    if repository_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Localized repository file not found",
        )

    proposal = generate_repair_proposal(
        repository_file,
    )

    candidate = RepairCandidate(
        incident_id=incident_id,
        file_id=repository_file.id,
        file_path=repository_file.path,
        repair_type=proposal.repair_type,
        summary=proposal.summary,
        rationale=proposal.rationale,
        original_content=proposal.original_content,
        proposed_content=proposal.proposed_content,
        diff=proposal.diff,
        risk_level=proposal.risk_level,
        validation_checks=proposal.validation_checks,
        status="proposed",
    )

    db.add(candidate)

    await db.commit()
    await db.refresh(candidate)

    candidate_merged_at: datetime | None = candidate.merged_at

    return {
        "incident_id": str(incident.id),
        "repair_candidate": {
            "id": str(candidate.id),
            "file_id": str(candidate.file_id),
            "file_path": candidate.file_path,
            "repair_type": candidate.repair_type,
            "summary": candidate.summary,
            "rationale": candidate.rationale,
            "original_content": candidate.original_content,
            "proposed_content": candidate.proposed_content,
            "diff": candidate.diff,
            "risk_level": candidate.risk_level,
            "validation_checks": candidate.validation_checks,
            "status": candidate.status,
        },
        "localization": {
            "confidence": selected_match.confidence,
            "matched_signals": selected_match.matched_signals,
            "evidence": selected_match.evidence,
        },
    }


@router.post(
    "/{incident_id}/repair/{repair_id}/validate",
)
async def validate_incident_repair(
    incident_id: UUID,
    repair_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(
        Incident,
        incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    candidate = await db.get(
        RepairCandidate,
        repair_id,
    )

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repair candidate not found",
        )

    if candidate.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repair candidate does not belong to this incident",
        )

    if candidate.status not in {"proposed", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Repair candidate cannot be validated from "
                f"status '{candidate.status}'"
            ),
        )

    validation = validate_repair_candidate(candidate)

    candidate.status = validation.status
    candidate.validation_checks = validation.checks

    await db.commit()
    await db.refresh(candidate)

    return {
        "incident_id": str(incident.id),
        "repair_candidate": {
            "id": str(candidate.id),
            "file_id": str(candidate.file_id),
            "file_path": candidate.file_path,
            "repair_type": candidate.repair_type,
            "risk_level": candidate.risk_level,
            "status": candidate.status,
        },
        "validation": {
            "valid": validation.valid,
            "status": validation.status,
            "summary": validation.summary,
            "checks": validation.checks,
        },
    }


@router.post(
    "/{incident_id}/repair/{repair_id}/verify",
)
async def verify_incident_repair(
    incident_id: UUID,
    repair_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(
        Incident,
        incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    candidate = await db.get(
        RepairCandidate,
        repair_id,
    )

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repair candidate not found",
        )

    if candidate.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repair candidate does not belong to this incident",
        )

    if candidate.status != "validated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only validated repair candidates can be verified",
        )

    verification = verify_repair(
        original_content=candidate.original_content,
        proposed_content=candidate.proposed_content,
    )

    if verification.verified:
        candidate.status = "verified"
    else:
        candidate.status = "verification_failed"

    candidate.validation_checks = (
        candidate.validation_checks
        + verification.checks
    )

    await db.commit()
    await db.refresh(candidate)

    return {
        "incident_id": str(incident.id),
        "repair_candidate": {
            "id": str(candidate.id),
            "file_id": str(candidate.file_id),
            "file_path": candidate.file_path,
            "repair_type": candidate.repair_type,
            "risk_level": candidate.risk_level,
            "status": candidate.status,
        },
        "verification": {
            "verified": verification.verified,
            "status": verification.status,
            "summary": verification.summary,
            "checks": verification.checks,
        },
    }


@router.post(
    "/{incident_id}/repair/{repair_id}/pr",
)
async def create_incident_repair_pull_request(
    incident_id: UUID,
    repair_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(
        Incident,
        incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    candidate = await db.get(
        RepairCandidate,
        repair_id,
    )

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repair candidate not found",
        )

    if candidate.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repair candidate does not belong to this incident",
        )

    if candidate.status != "verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only verified repair candidates can "
                "create a pull request"
            ),
        )

    repository_result = await db.execute(
        select(Repository)
        .where(
            Repository.project_id == incident.project_id
        )
        .order_by(Repository.created_at.asc())
    )

    repository = repository_result.scalars().first()

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found for incident project",
        )

    try:
        pull_request = await create_repair_pull_request(
            owner=repository.owner,
            repository=repository.name,
            base_branch=repository.default_branch,
            file_path=candidate.file_path,
            original_content=candidate.original_content,
            proposed_content=candidate.proposed_content,
            incident_id=str(incident.id),
            repair_candidate_id=str(candidate.id),
        )
    except GitHubRemediationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    candidate.status = "pull_request_created"
    candidate.github_pr_number = pull_request.pull_request_number
    candidate.github_pr_branch = pull_request.branch
    candidate.github_commit_sha = pull_request.commit_sha
    candidate.github_pr_url = pull_request.pull_request_url

    await db.commit()
    await db.refresh(candidate)

    return {
        "incident_id": str(incident.id),
        "repair_candidate": {
            "id": str(candidate.id),
            "file_id": str(candidate.file_id),
            "file_path": candidate.file_path,
            "repair_type": candidate.repair_type,
            "risk_level": candidate.risk_level,
            "status": candidate.status,
        },
        "repository": {
            "provider": repository.provider,
            "owner": repository.owner,
            "name": repository.name,
            "base_branch": repository.default_branch,
        },
        "pull_request": {
            "number": pull_request.pull_request_number,
            "branch": pull_request.branch,
            "commit_sha": pull_request.commit_sha,
            "url": pull_request.pull_request_url,
        },
    }


@router.post(
    "/{incident_id}/repair/{repair_id}/sync",
)
async def sync_incident_repair(
    incident_id: UUID,
    repair_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(
        Incident,
        incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    candidate = await db.get(
        RepairCandidate,
        repair_id,
    )

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repair candidate not found",
        )

    if candidate.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repair candidate does not belong to this incident",
        )

    if candidate.github_pr_number is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repair candidate does not have a GitHub pull request",
        )

    if candidate.status not in {
        "pull_request_created",
        "applied",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Repair candidate cannot be synchronized from "
                f"status '{candidate.status}'"
            ),
        )

    repository_result = await db.execute(
        select(Repository).where(
            Repository.project_id == incident.project_id
        )
    )

    repository = repository_result.scalars().first()

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found for incident project",
        )

    try:
        github_status = await get_pull_request_status(
            owner=repository.owner,
            repository=repository.name,
            pull_request_number=candidate.github_pr_number,
        )
    except GitHubRemediationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    if not github_status.merged:
        github_merged_at: datetime | None = github_status.merged_at

        return {
            "incident_id": str(incident.id),
            "repair_candidate": {
                "id": str(candidate.id),
                "file_path": candidate.file_path,
                "status": candidate.status,
                "github_pr_number": candidate.github_pr_number,
                "github_pr_url": candidate.github_pr_url,
            },
            "github": {
                "state": github_status.state,
                "merged": github_status.merged,
                "merged_at": (
                    github_merged_at.isoformat()
                    if github_merged_at is not None
                    else None
                ),
                "merge_commit_sha": github_status.merge_commit_sha,
                "head_branch": github_status.head_branch,
                "base_branch": github_status.base_branch,
                "url": github_status.html_url,
            },
            "synchronized": False,
            "message": "GitHub pull request has not been merged",
        }

    candidate.status = "applied"
    candidate.github_pr_number = github_status.number
    candidate.github_pr_branch = github_status.head_branch
    candidate.github_commit_sha = github_status.merge_commit_sha
    candidate.github_pr_url = github_status.html_url
    candidate.merged_at = github_status.merged_at

    await db.commit()
    await db.refresh(candidate)

    candidate_merged_at: datetime | None = candidate.merged_at

    return {
        "incident_id": str(incident.id),
        "repair_candidate": {
            "id": str(candidate.id),
            "file_id": str(candidate.file_id),
            "file_path": candidate.file_path,
            "repair_type": candidate.repair_type,
            "risk_level": candidate.risk_level,
            "status": candidate.status,
            "github_pr_number": candidate.github_pr_number,
            "github_pr_branch": candidate.github_pr_branch,
            "github_commit_sha": candidate.github_commit_sha,
            "github_pr_url": candidate.github_pr_url,
            "merged_at": (
                candidate_merged_at.isoformat()
                if candidate_merged_at is not None
                else None
            ),
        },
        "github": {
            "state": github_status.state,
            "merged": github_status.merged,
            "merge_commit_sha": github_status.merge_commit_sha,
            "head_branch": github_status.head_branch,
            "base_branch": github_status.base_branch,
            "url": github_status.html_url,
        },
        "synchronized": True,
        "message": "Merged GitHub repair synchronized successfully",
    }


