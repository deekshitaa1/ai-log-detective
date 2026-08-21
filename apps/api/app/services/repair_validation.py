import ast
from dataclasses import dataclass

from app.models import RepairCandidate


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    status: str
    checks: list[dict[str, object]]
    summary: str


def _syntax_check(content: str) -> tuple[bool, str]:
    try:
        ast.parse(content)
        return True, "Python syntax is valid"
    except SyntaxError as exc:
        return False, (
            f"Python syntax error at line {exc.lineno}: {exc.msg}"
        )


def _content_changed(candidate: RepairCandidate) -> tuple[bool, str]:
    if candidate.original_content == candidate.proposed_content:
        return False, "Proposed content is identical to original content"

    return True, "Proposed content contains a change"


def _diff_exists(candidate: RepairCandidate) -> tuple[bool, str]:
    if not candidate.diff.strip():
        return False, "Repair diff is empty"

    return True, "Repair diff is non-empty"


def _repair_specific_check(
    candidate: RepairCandidate,
) -> tuple[bool, str]:
    if candidate.repair_type != "database-connectivity-hardening":
        return True, "No specialized database repair check required"

    proposed = candidate.proposed_content

    required_patterns = [
        "for attempt in range(3):",
        "try:",
        "except TimeoutError:",
        "if attempt == 2:",
        "raise",
    ]

    missing = [
        pattern
        for pattern in required_patterns
        if pattern not in proposed
    ]

    if missing:
        return False, (
            "Database repair is missing required retry handling: "
            + ", ".join(missing)
        )

    return True, "Bounded database retry handling is present"


def validate_repair_candidate(
    candidate: RepairCandidate,
) -> ValidationResult:

    checks: list[dict[str, object]] = []

    syntax_ok, syntax_message = _syntax_check(
        candidate.proposed_content
    )

    checks.append(
        {
            "name": "python-syntax",
            "passed": syntax_ok,
            "message": syntax_message,
        }
    )

    changed_ok, changed_message = _content_changed(
        candidate
    )

    checks.append(
        {
            "name": "content-change",
            "passed": changed_ok,
            "message": changed_message,
        }
    )

    diff_ok, diff_message = _diff_exists(candidate)

    checks.append(
        {
            "name": "diff-integrity",
            "passed": diff_ok,
            "message": diff_message,
        }
    )

    repair_ok, repair_message = _repair_specific_check(
        candidate
    )

    checks.append(
        {
            "name": "repair-specific",
            "passed": repair_ok,
            "message": repair_message,
        }
    )

    valid = all(
        bool(check["passed"])
        for check in checks
    )

    if valid:
        return ValidationResult(
            valid=True,
            status="validated",
            checks=checks,
            summary="All repair validation checks passed",
        )

    return ValidationResult(
        valid=False,
        status="rejected",
        checks=checks,
        summary="One or more repair validation checks failed",
    )
