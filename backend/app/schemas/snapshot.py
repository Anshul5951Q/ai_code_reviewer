"""
Pydantic schemas for repository snapshot API responses.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator


class LanguageStat(BaseModel):
    files: int
    percentage: float


class DependencyInfo(BaseModel):
    name: str
    version: Optional[str] = None
    type: str  # dependency | dev_dependency | peer_dependency | optional
    source_file: str


class RepositoryStructure(BaseModel):
    entry_points: List[str] = []
    largest_files: List[Dict[str, Any]] = []
    directory_structure: Dict[str, int] = {}
    total_dependencies: int = 0


class RepositorySnapshotResponse(BaseModel):
    """Serialized repository snapshot with parsed JSON fields."""
    id: str
    review_id: str
    commit_sha: str
    branch: str

    total_files: int
    source_files: int
    test_files: int
    config_files: int
    total_lines: int

    languages: Dict[str, LanguageStat] = {}
    frameworks: List[str] = []
    dependencies: List[DependencyInfo] = []
    structure: Optional[RepositoryStructure] = None

    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("languages", mode="before")
    @classmethod
    def parse_languages(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v or {}

    @field_validator("frameworks", mode="before")
    @classmethod
    def parse_frameworks(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v or []

    @field_validator("dependencies", mode="before")
    @classmethod
    def parse_dependencies(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v or []

    @field_validator("structure", mode="before")
    @classmethod
    def parse_structure(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v
