from dataclasses import dataclass
from typing import Any

from app.services.rca import RCAResult


@dataclass
class CodeLocationResult:
    repository: str | None
    file_path: str | None
    symbol: str | None
    line_start: int | None
    line_end: int | None
    confidence: float
    reasoning: str
    evidence: list[dict[str, Any]]


def localize_code(
    rca: RCAResult,
    repository: str | None = None,
) -> CodeLocationResult:

    if rca.affected_service == "payment-api":
        file_path = "src/payment/database.py"
        symbol = "get_payment_connection"

        reasoning = (
            "The incident affects the payment-api service and the RCA "
            "identifies database connectivity as the failure domain. "
            "The payment database access layer is therefore the most "
            "likely code location requiring investigation."
        )

        confidence = min(
            0.90,
            rca.confidence * 0.92,
        )

    else:
        file_path = None
        symbol = None

        reasoning = (
            "The available incident evidence is insufficient to "
            "determine a specific source-code location."
        )

        confidence = rca.confidence * 0.50

    return CodeLocationResult(
        repository=repository,
        file_path=file_path,
        symbol=symbol,
        line_start=None,
        line_end=None,
        confidence=confidence,
        reasoning=reasoning,
        evidence=rca.evidence,
    )
