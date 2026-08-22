import ast
from dataclasses import dataclass
from difflib import unified_diff

from app.models import RepositoryFile


@dataclass(frozen=True)
class RepairProposal:
    repair_type: str
    summary: str
    rationale: str
    original_content: str
    proposed_content: str
    diff: str
    risk_level: str
    validation_checks: list[str]


def _normalize_content(content: str) -> str:
    if not isinstance(content, str):
        return ""

    content = content.lstrip("\ufeff")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    return content


def _is_valid_python(content: str) -> bool:
    try:
        ast.parse(content)
        return True
    except SyntaxError:
        return False


def _generate_database_timeout_repair(
    content: str,
) -> str | None:

    old_block = """    await asyncio.sleep(0.01)

    raise TimeoutError(
        f"Database connection timeout: {DATABASE_HOST}"
    )
"""

    new_block = """    for attempt in range(3):
        try:
            await asyncio.sleep(0.01)

            raise TimeoutError(
                f"Database connection timeout: {DATABASE_HOST}"
            )

        except TimeoutError:
            if attempt == 2:
                raise
"""

    if content.count(old_block) != 1:
        return None

    proposed = content.replace(old_block, new_block, 1)

    if not _is_valid_python(proposed):
        return None

    return proposed


def _manual_proposal(
    original: str,
    reason: str,
) -> RepairProposal:

    return RepairProposal(
        repair_type="manual-investigation-required",
        summary="No safe automatic repair pattern was identified.",
        rationale=reason,
        original_content=original,
        proposed_content=original,
        diff="",
        risk_level="high",
        validation_checks=[
            "Manual code review required",
            "Python syntax validation",
        ],
    )


def generate_repair_proposal(
    repository_file: RepositoryFile,
) -> RepairProposal:

    original = _normalize_content(
        repository_file.content or ""
    )

    if repository_file.language not in (None, "python"):
        return _manual_proposal(
            original,
            "The current repair engine only supports Python.",
        )

    if not _is_valid_python(original):
        return _manual_proposal(
            original,
            "The localized repository source is not valid Python. "
            "The repair engine refuses to modify malformed source.",
        )

    proposed = _generate_database_timeout_repair(original)

    if proposed is None:
        return _manual_proposal(
            original,
            "The source did not match the exact validated "
            "database-timeout repair pattern.",
        )

    diff = "".join(
        unified_diff(
            original.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            fromfile=repository_file.path,
            tofile=repository_file.path,
        )
    )

    return RepairProposal(
        repair_type="database-connectivity-hardening",
        summary=(
            "Add bounded retry handling to the database "
            "connection boundary."
        ),
        rationale=(
            "The database connection boundary was identified as "
            "the highest-confidence source of the timeout. "
            "The repair adds exactly three bounded attempts while "
            "preserving the final TimeoutError."
        ),
        original_content=original,
        proposed_content=proposed,
        diff=diff,
        risk_level="medium",
        validation_checks=[
            "Python syntax validation",
            "Verify retry count is exactly three attempts",
            "Verify final TimeoutError is preserved",
            "Verify payment endpoint error handling remains intact",
            "Verify no unrelated files are modified",
        ],
    )
