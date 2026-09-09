from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.review import Review


class AgentRun(Base):
    """Tracks execution of an individual analysis agent for a review."""

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Agent type: code_understanding | code_review | security_static | security_agent
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Status: queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    files_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    findings_generated: Mapped[int] = mapped_column(Integer, default=0)

    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="agent_runs")

    def __repr__(self) -> str:
        return f"<AgentRun {self.agent_type!r} status={self.status!r}>"
