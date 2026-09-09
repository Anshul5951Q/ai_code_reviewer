from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RepositoryCreate(BaseModel):
    """Payload to create or register a repository."""
    name: str = Field(..., min_length=1, max_length=255)
    full_name: str = Field(..., min_length=3, max_length=512)
    owner: str = Field(..., min_length=1, max_length=255)
    default_branch: str = Field(default="main", max_length=255)
    visibility: str = Field(default="public", max_length=32)
    language: Optional[str] = Field(default=None, max_length=128)
    github_id: Optional[int] = None


class RepositoryImportRequest(BaseModel):
    """Payload to import a repository directly by its GitHub full name (owner/repo)."""
    full_name: str = Field(..., min_length=3, max_length=512)


class RepositoryResponse(BaseModel):
    """Serialized representation of a repository."""

    id: str
    name: str
    full_name: str
    owner: str
    default_branch: str
    visibility: str
    language: Optional[str] = None
    github_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepositoryListResponse(BaseModel):
    """Paginated list of repositories."""

    items: List[RepositoryResponse] = Field(default_factory=list)
    total: int = 0
