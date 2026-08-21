from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import Detection, Incident
from app.services.correlation import CorrelationResult


@dataclass(frozen=True)
class EvidenceItem:
    category: str
    signal: str
    confidence: float
    details: dict[str, Any]


@dataclass(frozen=True)
class InvestigationEvidence:
    incident_id: str
    incident_title: str
    incident_description: str | None
    severity: str
    failure_domain: str
    primary_service: str | None
    suspected_dependency: str | None
    failure_pattern: str
    overall_confidence: float
    items: list[EvidenceItem]


def aggregate_incident_evidence(
    *,
    incident: Incident,
    detections: list[Detection],
    correlation: CorrelationResult,
) -> InvestigationEvidence:
    items: list[EvidenceItem] = []

    for detection in detections:
        evidence = detection.evidence or {}

        items.append(
            EvidenceItem(
                category=detection.detector,
                signal=detection.signal,
                confidence=float(detection.confidence),
                details=evidence,
            )
        )

    if correlation.primary_service:
        items.append(
            EvidenceItem(
                category="correlation",
                signal=f"Affected service: {correlation.primary_service}",
                confidence=correlation.confidence,
                details={
                    "service": correlation.primary_service,
                },
            )
        )

    if correlation.suspected_dependency:
        items.append(
            EvidenceItem(
                category="correlation",
                signal=(
                    f"Suspected dependency: "
                    f"{correlation.suspected_dependency}"
                ),
                confidence=correlation.confidence,
                details={
                    "dependency": correlation.suspected_dependency,
                },
            )
        )

    if correlation.failure_pattern:
        items.append(
            EvidenceItem(
                category="correlation",
                signal=correlation.failure_pattern,
                confidence=correlation.confidence,
                details={
                    "failure_domain": correlation.failure_domain,
                },
            )
        )

    confidence_values = [
        item.confidence
        for item in items
        if item.confidence is not None
    ]

    overall_confidence = (
        max(confidence_values)
        if confidence_values
        else float(correlation.confidence)
    )

    return InvestigationEvidence(
        incident_id=str(incident.id),
        incident_title=incident.title,
        incident_description=incident.description,
        severity=incident.severity,
        failure_domain=correlation.failure_domain,
        primary_service=correlation.primary_service,
        suspected_dependency=correlation.suspected_dependency,
        failure_pattern=correlation.failure_pattern,
        overall_confidence=overall_confidence,
        items=items,
    )
