from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.finding_relationship import FindingRelationship
    from app.models.remediation_run import RemediationRun
    from app.models.review import Review


class Finding(Base):
    """Represents a single security or quality finding from a code review."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Classification
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # Categories: security | quality | style | performance | dependency
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Severities: critical | high | medium | low | info

    # Content
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Location
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Detailed classification & evidence
    type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    cwe: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, default="code_review_agent")

    # Confidence score 0.0 - 1.0
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    # Statuses: open | resolved | ignored | false_positive

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="findings")
    remediation_runs: Mapped[List["RemediationRun"]] = relationship(
        "RemediationRun", back_populates="finding", cascade="all, delete-orphan"
    )
    finding_relationships: Mapped[List["FindingRelationship"]] = relationship(
        "FindingRelationship", back_populates="source_finding", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Finding {self.title!r} severity={self.severity!r}>"
