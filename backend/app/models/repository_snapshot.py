from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.review import Review


class RepositorySnapshot(Base):
    """
    Structured snapshot of a repository at a specific commit.

    Stores deterministic analysis results (languages, dependencies, structure)
    as JSON-serialized text. This becomes the primary input to the Phase 5
    multi-agent system.
    """

    __tablename__ = "repository_snapshots"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one snapshot per review
        index=True,
    )

    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    branch: Mapped[str] = mapped_column(String(255), nullable=False)

    # File statistics
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    source_files: Mapped[int] = mapped_column(Integer, default=0)
    test_files: Mapped[int] = mapped_column(Integer, default=0)
    config_files: Mapped[int] = mapped_column(Integer, default=0)
    total_lines: Mapped[int] = mapped_column(Integer, default=0)

    # JSON-serialized structured data (Text for SQLite/PostgreSQL compatibility)
    # {"typescript": {"files": 182, "percentage": 71.4}, ...}
    languages: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ["react", "next.js", "tailwind", ...]
    frameworks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # [{"name": "react", "version": "^18.0.0", "type": "dependency", "source_file": "package.json"}, ...]
    dependencies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # {"entry_points": [...], "largest_files": [...], "directory_tree": {...}}
    structure: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="snapshot")

    def __repr__(self) -> str:
        return f"<RepositorySnapshot review={self.review_id!r} commit={self.commit_sha[:7]!r}>"
