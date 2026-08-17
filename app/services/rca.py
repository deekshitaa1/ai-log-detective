from dataclasses import dataclass
from typing import Any

from app.services.correlation import CorrelationResult


@dataclass
class RCAResult:
    root_cause: str
    explanation: str
    affected_service: str
    affected_dependency: str | None
    confidence: float
    evidence: list[dict[str, Any]]
    recommended_actions: list[str]


def analyze_root_cause(
    correlation: CorrelationResult,
) -> RCAResult:

    if correlation.failure_domain == "database_connectivity":
        dependency = correlation.suspected_dependency or "database"

        root_cause = (
            f"Database connectivity failure involving {dependency}"
        )

        explanation = (
            f"The {correlation.primary_service} service is experiencing "
            f"database connectivity timeouts against {dependency}. "
            f"The detection signals indicate a timeout-based failure "
            f"pattern rather than a generic application exception."
        )

        recommended_actions = [
            f"Check connectivity from {correlation.primary_service} to {dependency}.",
            f"Inspect connection pool saturation for {dependency}.",
            f"Check database health, latency, and active connections.",
            "Review recent deployments or configuration changes.",
            "Verify timeout and retry configuration.",
        ]

    else:
        root_cause = (
            f"Unclassified application failure in "
            f"{correlation.primary_service}"
        )

        explanation = (
            "The available detection evidence indicates an application "
            "failure, but there is insufficient evidence to identify a "
            "more specific root cause."
        )

        recommended_actions = [
            "Collect additional application logs.",
            "Correlate metrics and traces around the incident window.",
            "Inspect recent deployments and configuration changes.",
        ]

    return RCAResult(
        root_cause=root_cause,
        explanation=explanation,
        affected_service=correlation.primary_service,
        affected_dependency=correlation.suspected_dependency,
        confidence=correlation.confidence,
        evidence=correlation.evidence,
        recommended_actions=recommended_actions,
    )
