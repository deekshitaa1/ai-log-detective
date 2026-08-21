from dataclasses import dataclass

from app.models import Detection


@dataclass(frozen=True)
class CorrelationResult:
    failure_domain: str
    primary_service: str | None
    suspected_dependency: str | None
    failure_pattern: str
    confidence: float


def correlate_detections(
    detections: list[Detection],
) -> CorrelationResult:

    if not detections:
        return CorrelationResult(
            failure_domain="unknown",
            primary_service=None,
            suspected_dependency=None,
            failure_pattern="No correlated failure signals",
            confidence=0.0,
        )

    database_signals = [
        detection
        for detection in detections
        if detection.detector == "database-timeout-detector"
    ]

    if database_signals:
        evidence = database_signals[0].evidence or {}

        metadata = evidence.get("metadata") or {}

        service = evidence.get("service")
        database = metadata.get("database")

        return CorrelationResult(
            failure_domain="database_connectivity",
            primary_service=service,
            suspected_dependency=database,
            failure_pattern="Database connectivity timeout",
            confidence=max(
                detection.confidence
                for detection in database_signals
            ),
        )

    services = []

    for detection in detections:
        evidence = detection.evidence or {}
        service = evidence.get("service")

        if service and service not in services:
            services.append(service)

    return CorrelationResult(
        failure_domain="application_failure",
        primary_service=services[0] if services else None,
        suspected_dependency=None,
        failure_pattern="Application failure signals detected",
        confidence=max(
            detection.confidence
            for detection in detections
        ),
    )
