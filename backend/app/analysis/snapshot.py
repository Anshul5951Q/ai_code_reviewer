"""
Repository snapshot builder.

Transforms RepositoryIntelligence + analysis results into a structured
RepositorySnapshot data object suitable for database persistence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.analysis.dependency_analyzer import Dependency
from app.analysis.language_detector import LanguageStat
from app.analysis.repository_intelligence import RepositoryIntelligence


@dataclass
class RepositorySnapshotData:
    """
    Serializable snapshot of a repository at a specific commit.
    
    This is the primary input to the future multi-agent system.
    """
    review_id: str
    commit_sha: str
    branch: str

    # File statistics
    total_files: int = 0
    source_files: int = 0
    test_files: int = 0
    config_files: int = 0
    total_lines: int = 0

    # JSON-serialized data for DB storage
    languages_json: str = "{}"
    frameworks_json: str = "[]"
    dependencies_json: str = "[]"
    structure_json: str = "{}"

    def to_db_kwargs(self) -> dict:
        """Return kwargs for creating a RepositorySnapshot ORM model."""
        return {
            "review_id": self.review_id,
            "commit_sha": self.commit_sha,
            "branch": self.branch,
            "total_files": self.total_files,
            "source_files": self.source_files,
            "test_files": self.test_files,
            "config_files": self.config_files,
            "total_lines": self.total_lines,
            "languages": self.languages_json,
            "frameworks": self.frameworks_json,
            "dependencies": self.dependencies_json,
            "structure": self.structure_json,
        }


def build_snapshot(
    review_id: str,
    commit_sha: str,
    branch: str,
    intelligence: RepositoryIntelligence,
    dependencies: List[Dependency],
) -> RepositorySnapshotData:
    """
    Build a RepositorySnapshotData from analysis results.

    Parameters
    ----------
    review_id:
        ID of the associated Review record.
    commit_sha:
        Full commit SHA being analyzed.
    branch:
        Branch name the commit is on.
    intelligence:
        RepositoryIntelligence from analyze_repository().
    dependencies:
        Dependency list from analyze_dependencies().

    Returns
    -------
    RepositorySnapshotData ready for database persistence.
    """
    languages_data = {
        lang: stat.to_dict()
        for lang, stat in intelligence.languages.items()
    }

    dependencies_data = [dep.to_dict() for dep in dependencies]

    structure_data = {
        "entry_points": intelligence.entry_points,
        "largest_files": intelligence.largest_files,
        "directory_structure": intelligence.directory_structure,
        "total_dependencies": intelligence.total_dependencies,
    }

    return RepositorySnapshotData(
        review_id=review_id,
        commit_sha=commit_sha,
        branch=branch,
        total_files=intelligence.total_files,
        source_files=intelligence.source_files,
        test_files=intelligence.test_files,
        config_files=intelligence.config_files,
        total_lines=intelligence.total_lines,
        languages_json=json.dumps(languages_data),
        frameworks_json=json.dumps(intelligence.frameworks),
        dependencies_json=json.dumps(dependencies_data),
        structure_json=json.dumps(structure_data),
    )
