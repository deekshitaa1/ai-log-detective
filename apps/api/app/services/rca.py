from __future__ import annotations

from dataclasses import dataclass

from app.models import Detection, Incident
from app.services.correlation import CorrelationResult
from app.services.evidence import InvestigationEvidence


@dataclass(frozen=True)
class RCAResult:
    root_cause: str
    explanation: str
    confidence: float
    affected_service: str | None
    dependency: str | None
    impact: str
    evidence: list[str]
    recommended_checks: list[str]


def analyze_root_cause(
    incident: Incident,
    correlation: CorrelationResult,
    detections: list[Detection],
    investigation: InvestigationEvidence | None = None,
) -> RCAResult:

    if investigation is not None:
        evidence = [
            item.signal
            for item in investigation.items
            if item.signal
        ]

        confidence = investigation.overall_confidence
    else:
        evidence = [
            detection.signal
            for detection in detections
            if detection.signal
        ]

        confidence = correlation.confidence

    if not detections:
        return RCAResult(
            root_cause="Unknown",
            explanation=(
                "No persisted detection signals were available "
                "for this incident."
            ),
            confidence=0.0,
            affected_service=correlation.primary_service,
            dependency=correlation.suspected_dependency,
            impact=(
                "The impact could not be determined because "
                "there is insufficient evidence."
            ),
            evidence=evidence,
            recommended_checks=[
                "Collect application logs",
                "Run incident detection",
                "Verify service health",
            ],
        )

    if correlation.failure_domain == "database_connectivity":
        service = correlation.primary_service
        dependency = correlation.suspected_dependency

        return RCAResult(
            root_cause="Database connectivity failure",
            explanation=(
                f"{service or 'The affected service'} is experiencing "
                f"database connectivity timeouts while communicating "
                f"with {dependency or 'the suspected database dependency'}."
            ),
            confidence=confidence,
            affected_service=service,
            dependency=dependency,
            impact=(
                f"Requests handled by "
                f"{service or 'the affected service'} "
                "may fail or experience significant latency."
            ),
            evidence=evidence,
            recommended_checks=[
                "Check database availability and health",
                "Check database connection pool saturation",
                "Check network connectivity between the service and database",
                "Check database connection timeout configuration",
                "Check recent database or infrastructure changes",
            ],
        )

    if correlation.failure_domain == "application_failure":
        service = correlation.primary_service

        return RCAResult(
            root_cause="Application failure",
            explanation=(
                f"Application failure signals were detected in "
                f"{service or 'the affected service'}."
            ),
            confidence=confidence,
            affected_service=service,
            dependency=None,
            impact=(
                f"Requests handled by "
                f"{service or 'the affected service'} "
                "may fail or return degraded responses."
            ),
            evidence=evidence,
            recommended_checks=[
                "Inspect application error logs",
                "Inspect recent application changes",
                "Check service health",
                "Check application dependencies",
            ],
        )

    return RCAResult(
        root_cause="Unknown failure domain",
        explanation=(
            "The available detection signals do not provide "
            "enough evidence to determine a specific root cause."
        ),
        confidence=confidence,
        affected_service=correlation.primary_service,
        dependency=correlation.suspected_dependency,
        impact=(
            "The incident may affect application availability "
            "or request latency."
        ),
        evidence=evidence,
        recommended_checks=[
            "Inspect all incident logs",
            "Inspect service dependencies",
            "Check recent deployments",
            "Check infrastructure health",
        ],
    )
