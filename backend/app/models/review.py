from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.analysis_job import AnalysisJob
    from app.models.correlated_finding import CorrelatedFinding
    from app.models.finding import Finding
    from app.models.remediation_run import RemediationRun
    from app.models.repository import Repository
    from app.models.repository_snapshot import RepositorySnapshot
    from app.models.verification_run import VerificationRun


class Review(Base):
    """Represents a code review analysis run on a repository commit."""

    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    branch: Mapped[str] = mapped_column(String(255), nullable=False)

    # Review lifecycle status
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    # Statuses: queued | ingesting | ready_for_analysis | running | completed | completed_with_warnings | failed | cancelled

    # Scores — null until analysis completes
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    security_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    architecture_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(
        "Repository", back_populates="reviews"
    )
    findings: Mapped[List["Finding"]] = relationship(
        "Finding", back_populates="review", cascade="all, delete-orphan"
    )
    analysis_jobs: Mapped[List["AnalysisJob"]] = relationship(
        "AnalysisJob", back_populates="review", cascade="all, delete-orphan"
    )
    snapshot: Mapped[Optional["RepositorySnapshot"]] = relationship(
        "RepositorySnapshot", back_populates="review", uselist=False, cascade="all, delete-orphan"
    )
    agent_runs: Mapped[List["AgentRun"]] = relationship(
        "AgentRun", back_populates="review", cascade="all, delete-orphan"
    )
    remediation_runs: Mapped[List["RemediationRun"]] = relationship(
        "RemediationRun", back_populates="review", cascade="all, delete-orphan"
    )
    correlated_findings: Mapped[List["CorrelatedFinding"]] = relationship(
        "CorrelatedFinding", back_populates="review", cascade="all, delete-orphan"
    )
    verification_runs: Mapped[List["VerificationRun"]] = relationship(
        "VerificationRun", back_populates="review", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Review {self.id!r} status={self.status!r}>"
