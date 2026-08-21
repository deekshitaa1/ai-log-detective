from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Detection, RepositoryFile


@dataclass(frozen=True)
class LocalizationResult:
    file_id: str
    path: str
    language: str | None
    confidence: float
    role: str
    matched_signals: list[str]
    evidence: list[str]
    score: float
    reasons: list[str]


def _normalize(value: str) -> str:
    value = value.lower()
    value = value.replace("_", " ")
    value = value.replace("-", " ")
    value = re.sub(r"[^a-z0-9./ ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _extract_signal_terms(
    detections: list[Detection],
) -> list[str]:

    terms: list[str] = []

    for detection in detections:

        values = [
            detection.signal,
        ]

        evidence = detection.evidence or {}

        values.extend(
            [
                evidence.get("service"),
                evidence.get("message"),
            ]
        )

        metadata = evidence.get("metadata") or {}

        values.extend(
            [
                metadata.get("database"),
                metadata.get("endpoint"),
                metadata.get("error_code"),
                metadata.get("region"),
            ]
        )

        for value in values:

            if not value:
                continue

            normalized = _normalize(str(value))

            for token in normalized.split():

                if len(token) < 4:
                    continue

                if token not in terms:
                    terms.append(token)

    return terms


def _collect_evidence(
    content: str,
    signals: list[str],
) -> list[str]:

    lines = content.splitlines()

    candidates: list[tuple[int, int, str]] = []

    for number, line in enumerate(lines, start=1):

        normalized = _normalize(line)

        matched = sum(
            1
            for signal in signals
            if signal in normalized
        )

        strong_signal = any(
            phrase in normalized
            for phrase in [
                "raise timeout",
                "timeout error",
                "database connection timeout",
                "get database connection",
                "db timeout",
                "payments primary",
                "database connection",
                "timeouterror",
            ]
        )

        if matched > 0 or strong_signal:

            score = matched

            if strong_signal:
                score += 10

            candidates.append(
                (
                    score,
                    number,
                    line.strip(),
                )
            )

    candidates.sort(
        key=lambda item: (
            item[0],
            -item[1],
        ),
        reverse=True,
    )

    selected: list[str] = []

    for _, number, line in candidates:

        evidence = f"line {number}: {line}"

        if evidence not in selected:
            selected.append(evidence)

        if len(selected) >= 8:
            break

    selected.sort(
        key=lambda value: int(
            re.search(r"line (\d+):", value).group(1)
        )
    )

    return selected


def localize_detections(
    detections: list[Detection],
    files: list[RepositoryFile],
) -> list[LocalizationResult]:

    if not detections or not files:
        return []

    signals = _extract_signal_terms(detections)

    results: list[LocalizationResult] = []

    for repository_file in files:

        content = repository_file.content or ""

        normalized_content = _normalize(content)
        path_lower = repository_file.path.lower()

        matched_signals = [
            signal
            for signal in signals
            if signal in normalized_content
        ]

        if not matched_signals:
            continue

        score = 0.0
        reasons: list[str] = []

        # ---------------------------------------------------------
        # Signal matching
        # ---------------------------------------------------------

        signal_score = min(
            10.0,
            float(len(matched_signals)) * 1.5,
        )

        score += signal_score

        reasons.append(
            f"{len(matched_signals)} incident signal(s) "
            f"matched repository content"
        )

        # ---------------------------------------------------------
        # Strong failure indicators
        # ---------------------------------------------------------

        if "timeout" in normalized_content:
            score += 3.0
            reasons.append(
                "Contains timeout-related failure handling"
            )

        if "database" in normalized_content:
            score += 2.0
            reasons.append(
                "Contains database-related logic"
            )

        if "connection" in normalized_content:
            score += 2.0
            reasons.append(
                "Contains connection-related logic"
            )

        # ---------------------------------------------------------
        # Explicit database timeout boundary
        # ---------------------------------------------------------

        if "database connection timeout" in normalized_content:
            score += 8.0
            reasons.append(
                "Contains explicit database connection timeout"
            )

        if "get database connection" in normalized_content:
            score += 5.0
            reasons.append(
                "Contains database connection boundary"
            )

        if "raise timeout" in normalized_content:
            score += 8.0
            reasons.append(
                "Explicitly raises a timeout failure"
            )

        if "timeout error" in normalized_content:
            score += 8.0
            reasons.append(
                "Contains explicit TimeoutError handling"
            )

        if "timeouterror" in normalized_content:
            score += 5.0
            reasons.append(
                "Contains TimeoutError symbol"
            )

        # ---------------------------------------------------------
        # Payment/database-specific evidence
        # ---------------------------------------------------------

        if "payments primary" in normalized_content:
            score += 4.0
            reasons.append(
                "References the payments primary database"
            )

        if "db timeout" in normalized_content:
            score += 3.0
            reasons.append(
                "Contains database timeout terminology"
            )

        # ---------------------------------------------------------
        # File role classification
        # ---------------------------------------------------------

        role = "related_source"

        if path_lower.endswith("database.py"):

            role = "database_boundary"
            score += 5.0

            reasons.append(
                "File name identifies a database boundary"
            )

            if "get database connection" in normalized_content:
                score += 5.0

            if (
                "raise timeout" in normalized_content
                or "database connection timeout"
                in normalized_content
            ):
                score += 6.0

            role = "likely_root_cause"

        elif path_lower.endswith("payments.py"):

            role = "affected_caller"
            score += 3.0

            reasons.append(
                "File appears to be a payment service caller"
            )

            if "process payment" in normalized_content:
                score += 2.0
                reasons.append(
                    "Contains payment-processing logic"
                )

        elif path_lower.endswith("main.py"):

            role = "service_entrypoint"
            score -= 3.0

            reasons.append(
                "Service entrypoint receives a localization penalty"
            )

        # ---------------------------------------------------------
        # Documentation penalty
        # ---------------------------------------------------------

        if (
            repository_file.language == "markdown"
            or path_lower.endswith(".md")
        ):

            score -= 8.0
            role = "documentation"

            reasons.append(
                "Documentation file receives a localization penalty"
            )

        # ---------------------------------------------------------
        # Evidence extraction
        # ---------------------------------------------------------

        evidence = _collect_evidence(
            content,
            signals,
        )

        if evidence:
            score += min(
                6.0,
                len(evidence) * 0.75,
            )

            reasons.append(
                f"{len(evidence)} source-code evidence line(s) extracted"
            )

        # ---------------------------------------------------------
        # Confidence
        # ---------------------------------------------------------

        confidence = min(
            0.99,
            max(
                0.10,
                0.35 + (score * 0.035),
            ),
        )

        results.append(
            LocalizationResult(
                file_id=str(repository_file.id),
                path=repository_file.path,
                language=repository_file.language,
                confidence=round(confidence, 2),
                role=role,
                matched_signals=matched_signals[:15],
                evidence=evidence,
                score=round(score, 2),
                reasons=reasons,
            )
        )

    results.sort(
        key=lambda result: (
            result.confidence,
            result.score,
        ),
        reverse=True,
    )

    return results[:10]
