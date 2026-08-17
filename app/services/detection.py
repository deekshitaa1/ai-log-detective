from dataclasses import dataclass
from uuid import UUID

from app.models import LogEvent


@dataclass(frozen=True)
class DetectionSignal:
    detector: str
    signal: str
    confidence: float
    evidence: dict


def detect_log_event(log: LogEvent) -> list[DetectionSignal]:
    signals: list[DetectionSignal] = []

    level = log.level.upper()
    message = log.message.lower()
    metadata = log.metadata_json or {}

    # High-severity log detector
    if level in {"ERROR", "CRITICAL", "FATAL"}:
        confidence = 0.85 if level == "ERROR" else 0.95

        signals.append(
            DetectionSignal(
                detector="severity-detector",
                signal=f"High-severity log level detected: {level}",
                confidence=confidence,
                evidence={
                    "log_id": str(log.id),
                    "level": level,
                    "service": log.service,
                    "message": log.message,
                },
            )
        )

    # Database timeout detector
    timeout_terms = (
        "database connection timeout",
        "db timeout",
        "connection timeout",
        "database timeout",
        "timeout while connecting",
    )

    if any(term in message for term in timeout_terms):
        signals.append(
            DetectionSignal(
                detector="database-timeout-detector",
                signal="Database connection timeout detected",
                confidence=0.97,
                evidence={
                    "log_id": str(log.id),
                    "service": log.service,
                    "message": log.message,
                    "metadata": metadata,
                },
            )
        )

    # HTTP 5xx detector
    status_code = metadata.get("status_code")

    if isinstance(status_code, int) and 500 <= status_code <= 599:
        signals.append(
            DetectionSignal(
                detector="http-error-detector",
                signal=f"HTTP {status_code} server error detected",
                confidence=0.95,
                evidence={
                    "log_id": str(log.id),
                    "service": log.service,
                    "status_code": status_code,
                    "endpoint": metadata.get("endpoint"),
                },
            )
        )

    # Connection failure detector
    connection_terms = (
        "connection refused",
        "connection reset",
        "connection failed",
        "unable to connect",
        "connection failure",
    )

    if any(term in message for term in connection_terms):
        signals.append(
            DetectionSignal(
                detector="connection-failure-detector",
                signal="Service connection failure detected",
                confidence=0.92,
                evidence={
                    "log_id": str(log.id),
                    "service": log.service,
                    "message": log.message,
                },
            )
        )

    return signals
