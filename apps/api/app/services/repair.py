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
    """
    Normalize GitHub source content without changing its semantics.
    """
    if content.startswith("\ufeff"):
        content = content[1:]

    if content.startswith("ï»¿"):
        content = content[3:]

    return content.replace("\r\n", "\n").replace("\r", "\n")


def _generate_database_timeout_repair(
    content: str,
) -> str | None:
    """
    Generate one deterministic repair for the known database
    connectivity failure.

    The transformation is intentionally narrow: it replaces the
    existing database timeout operation with bounded retry handling.
    """

    old_block = '''    await asyncio.sleep(0.01)

    raise TimeoutError(
        f"Database connection timeout: {DATABASE_HOST}"
    )
'''

    new_block = '''    for attempt in range(3):
        try:
            await asyncio.sleep(0.01)

            raise TimeoutError(
                f"Database connection timeout: {DATABASE_HOST}"
            )

        except TimeoutError:
            if attempt == 2:
                raise
'''

    occurrences = content.count(old_block)

    if occurrences != 1:
        return None

    return content.replace(
        old_block,
        new_block,
        1,
    )


def generate_repair_proposal(
    repository_file: RepositoryFile,
) -> RepairProposal:
    original = _normalize_content(repository_file.content)

    proposed = _generate_database_timeout_repair(original)

    if proposed is None:
        return RepairProposal(
            repair_type="manual-investigation-required",
            summary=(
                "No safe automatic repair pattern was identified."
            ),
            rationale=(
                "The localized source did not match the exact "
                "database-timeout pattern required by the current "
                "safe repair engine."
            ),
            original_content=original,
            proposed_content=original,
            diff="",
            risk_level="high",
            validation_checks=[
                "Manual code review required",
            ],
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
            "Localization identified the database connection "
            "boundary as the highest-confidence source of the "
            "observed timeout. The proposed change adds a bounded "
            "three-attempt retry policy while preserving the final "
            "TimeoutError."
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
