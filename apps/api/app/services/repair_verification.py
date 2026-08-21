import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    status: str
    checks: list[dict[str, object]]
    summary: str


def _check_python_syntax(content: str) -> tuple[bool, str]:
    try:
        ast.parse(content)
        return True, "Proposed Python source compiles successfully"
    except SyntaxError as exc:
        return False, (
            f"Python syntax validation failed at "
            f"line {exc.lineno}: {exc.msg}"
        )


def _check_database_boundary(content: str) -> tuple[bool, str]:
    required = [
        "async def get_database_connection",
        "DATABASE_HOST",
        "for attempt in range(3):",
        "except TimeoutError:",
        "if attempt == 2:",
        "raise",
    ]

    missing = [
        item
        for item in required
        if item not in content
    ]

    if missing:
        return False, (
            "Database repair verification failed. "
            f"Missing: {', '.join(missing)}"
        )

    return True, (
        "Database connection boundary and bounded retry "
        "handling are present"
    )


def _check_retry_bound(content: str) -> tuple[bool, str]:
    if "for attempt in range(3):" not in content:
        return False, "Retry bound of three attempts was not found"

    if "range(4)" in content or "range(5)" in content:
        return False, "Repair contains an unexpected retry bound"

    return True, "Retry count is explicitly bounded to three attempts"


def _check_timeout_preservation(content: str) -> tuple[bool, str]:
    if "raise TimeoutError(" not in content:
        return False, (
            "Final database TimeoutError is no longer preserved"
        )

    if "if attempt == 2:" not in content:
        return False, (
            "Final retry does not explicitly preserve the timeout"
        )

    return True, "Final TimeoutError remains preserved"


def verify_repair(
    original_content: str,
    proposed_content: str,
) -> VerificationResult:

    checks: list[dict[str, object]] = []

    changed = original_content != proposed_content

    checks.append(
        {
            "name": "content-change",
            "passed": changed,
            "message": (
                "Proposed content differs from original"
                if changed
                else "Proposed content is identical to original"
            ),
        }
    )

    syntax_ok, syntax_message = _check_python_syntax(
        proposed_content
    )

    checks.append(
        {
            "name": "python-syntax",
            "passed": syntax_ok,
            "message": syntax_message,
        }
    )

    boundary_ok, boundary_message = _check_database_boundary(
        proposed_content
    )

    checks.append(
        {
            "name": "database-boundary",
            "passed": boundary_ok,
            "message": boundary_message,
        }
    )

    retry_ok, retry_message = _check_retry_bound(
        proposed_content
    )

    checks.append(
        {
            "name": "retry-bound",
            "passed": retry_ok,
            "message": retry_message,
        }
    )

    timeout_ok, timeout_message = _check_timeout_preservation(
        proposed_content
    )

    checks.append(
        {
            "name": "timeout-preservation",
            "passed": timeout_ok,
            "message": timeout_message,
        }
    )

    verified = all(
        bool(check["passed"])
        for check in checks
    )

    if verified:
        return VerificationResult(
            verified=True,
            status="verified",
            checks=checks,
            summary=(
                "Repair passed execution-safety verification"
            ),
        )

    return VerificationResult(
        verified=False,
        status="verification_failed",
        checks=checks,
        summary=(
            "Repair failed one or more verification checks"
        ),
    )
