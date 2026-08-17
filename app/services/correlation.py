from dataclasses import dataclass
from typing import Any

from app.models import Detection


@dataclass
class CorrelationResult:
    failure_domain: str
    primary_service: str
    suspected_dependency: str | None
    failure_pattern: str
    confidence: float
    evidence: list[dict[str, Any]]


def correlate_detections(
    detections: list[Detection],
) -> CorrelationResult:
    if not detections:
        return CorrelationResult(
            failure_domain="unknown",
            primary_service="unknown",
            suspected_dependency=None,
            failure_pattern="No detection signals available",
            confidence=0.0,
            evidence=[],
        )

    service_scores: dict[str, float] = {}
    database_scores: dict[str, float] = {}
    evidence: list[dict[str, Any]] = []

    failure_domain = "application"
    failure_pattern = "Application failure detected"

    for detection in detections:
        service = detection.evidence.get("service", "unknown")
        confidence = float(detection.confidence)

        service_scores[service] = (
            service_scores.get(service, 0.0) + confidence
        )

        evidence.append(
            {
                "detector": detection.detector,
                "signal": detection.signal,
                "confidence": detection.confidence,
                "evidence": detection.evidence,
            }
        )

        signal = detection.signal.lower()
        metadata = detection.evidence.get("metadata", {})

        database = metadata.get("database")

        if database:
            database_scores[database] = (
                database_scores.get(database, 0.0) + confidence
            )

        if "database" in signal or "timeout" in signal:
            failure_domain = "database_connectivity"
            failure_pattern = "Database connectivity timeout"

    primary_service = max(
        service_scores,
        key=service_scores.get,
        default="unknown",
    )

    suspected_dependency = (
        max(database_scores, key=database_scores.get)
        if database_scores
        else None
    )

    confidence = max(
        (float(d.confidence) for d in detections),
        default=0.0,
    )

    return CorrelationResult(
        failure_domain=failure_domain,
        primary_service=primary_service,
        suspected_dependency=suspected_dependency,
        failure_pattern=failure_pattern,
        confidence=confidence,
        evidence=evidence,
    )
