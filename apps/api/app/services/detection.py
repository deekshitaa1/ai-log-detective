from dataclasses import dataclass
from typing import Any

from app.models import LogEvent


@dataclass(frozen=True)
class DetectionSignal:
    detector: str
    signal: str
    confidence: float
    evidence: dict[str, Any]


def detect_log_event(log: LogEvent) -> list[DetectionSignal]:
    detections: list[DetectionSignal] = []

    message = log.message.lower()
    level = log.level.upper()

    # High-severity signal
    if level in {"ERROR", "CRITICAL", "FATAL"}:
        detections.append(
            DetectionSignal(
                detector="severity-detector",
                signal=f"High-severity log level detected: {level}",
                confidence=0.85,
                evidence={
                    "log_id": str(log.id),
                    "level": level,
                    "service": log.service,
                    "message": log.message,
                },
            )
        )

    # Database timeout signal
    timeout_terms = (
        "database connection timeout",
        "connection timeout",
        "db timeout",
        "database timeout",
        "timed out",
        "timeout while processing",
    )

    if any(term in message for term in timeout_terms):
        detections.append(
            DetectionSignal(
                detector="database-timeout-detector",
                signal="Database connection timeout detected",
                confidence=0.97,
                evidence={
                    "log_id": str(log.id),
                    "service": log.service,
                    "message": log.message,
                    "metadata": log.metadata_json,
                },
            )
        )

    # HTTP 5xx signal
    if any(code in message for code in ("500", "502", "503", "504")):
        detections.append(
            DetectionSignal(
                detector="http-5xx-detector",
                signal="HTTP 5xx failure detected",
                confidence=0.92,
                evidence={
                    "log_id": str(log.id),
                    "service": log.service,
                    "message": log.message,
                },
            )
        )

    # Authentication failure
    auth_terms = (
        "authentication failed",
        "unauthorized",
        "invalid token",
        "access denied",
    )

    if any(term in message for term in auth_terms):
        detections.append(
            DetectionSignal(
                detector="authentication-failure-detector",
                signal="Authentication or authorization failure detected",
                confidence=0.90,
                evidence={
                    "log_id": str(log.id),
                    "service": log.service,
                    "message": log.message,
                },
            )
        )

    return detections
