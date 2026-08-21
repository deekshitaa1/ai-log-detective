from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class RepairCandidate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "repair_candidates"

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_id: Mapped[str] = mapped_column(
        ForeignKey("repository_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    repair_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    rationale: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    original_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    proposed_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    diff: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    risk_level: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    validation_checks: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="proposed",
        index=True,
    )

    github_pr_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    github_pr_branch: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    github_commit_sha: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    github_pr_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    merged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
