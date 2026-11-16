from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.review import Review


class AnalysisJob(Base):
    """Tracks the lifecycle of a repository ingestion / analysis job."""

    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Lifecycle
    # queued | ingesting | indexing | analyzing | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)

    # Granular pipeline stage
    # repository_fetch | file_filtering | content_fetch | language_detection |
    # dependency_analysis | repository_intelligence | snapshot_creation | completed
    current_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Progress 0–100
    progress: Mapped[float] = mapped_column(Float, default=0.0)

    # File tracking
    files_total: Mapped[int] = mapped_column(Integer, default=0)
    files_processed: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Error message (safe, user-facing — no stack traces)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="analysis_jobs")

    def __repr__(self) -> str:
        return f"<AnalysisJob {self.id!r} status={self.status!r} stage={self.current_stage!r}>"

    @property
    def is_active(self) -> bool:
        """True if the job is in a non-terminal state."""
        norm = (self.status or "").lower()
        return norm in {
            "queued", "ingesting", "indexing", "analyzing", "running",
            "understanding", "correlating", "pending", "snapshotting",
            "quality_analysis", "security_analysis"
        }

    @property
    def is_terminal(self) -> bool:
        norm = (self.status or "").lower()
        return norm in {"completed", "failed", "cancelled", "partially_completed", "analysis_completed"}
