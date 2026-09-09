from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.review import Review


class Repository(Base):
    """Represents a GitHub repository connected to the platform."""

    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    visibility: Mapped[str] = mapped_column(String(32), default="private")
    language: Mapped[str | None] = mapped_column(String(128), nullable=True)
    github_id: Mapped[int | None] = mapped_column(nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    reviews: Mapped[List["Review"]] = relationship(
        "Review", back_populates="repository", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Repository {self.full_name!r}>"
