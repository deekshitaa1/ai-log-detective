from dataclasses import dataclass
from typing import Any

from app.services.code_localization import CodeLocationResult
from app.services.rca import RCAResult


@dataclass
class RepairProposalResult:
    title: str
    summary: str
    proposed_change: str
    file_path: str | None
    symbol: str | None
    confidence: float
    risk: str
    evidence: list[dict[str, Any]]
    validation_steps: list[str]


def propose_repair(
    rca: RCAResult,
    location: CodeLocationResult,
) -> RepairProposalResult:

    if (
        rca.affected_service == "payment-api"
        and rca.affected_dependency == "payments-primary"
        and location.file_path
    ):
        return RepairProposalResult(
            title="Harden payment database connectivity handling",
            summary=(
                "AegisAI identified a database connectivity failure "
                "affecting the payment service and localized the strongest "
                "repository candidate for investigation."
            ),
            proposed_change=(
                "Review the localized database-related code and harden "
                "connection timeout, retry, connection-pool, and failure "
                "handling. Preserve existing payment transaction semantics "
                "and never silently retry non-idempotent operations."
            ),
            file_path=location.file_path,
            symbol=location.symbol,
            confidence=min(
                0.95,
                rca.confidence * location.confidence,
            ),
            risk="medium",
            evidence=rca.evidence,
            validation_steps=[
                "Verify database connectivity from payment-api.",
                "Check connection-pool saturation.",
                "Verify timeout configuration.",
                "Test transient database connection failures.",
                "Run payment API integration tests.",
                "Verify no duplicate payment transactions occur.",
            ],
        )

    return RepairProposalResult(
        title="Investigation required",
        summary=(
            "AegisAI identified an incident but does not have enough "
            "evidence to safely propose a source-code change."
        ),
        proposed_change=(
            "Collect additional logs, repository context, and runtime "
            "evidence before generating a repair."
        ),
        file_path=location.file_path,
        symbol=location.symbol,
        confidence=min(
            rca.confidence,
            location.confidence,
        ),
        risk="high",
        evidence=rca.evidence,
        validation_steps=[
            "Collect additional incident evidence.",
            "Review the localized source code.",
            "Identify the exact failure mechanism.",
        ],
    )
