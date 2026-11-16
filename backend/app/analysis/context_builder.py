"""
Context builder for multi-agent code review.

Loads repository snapshot data, filters files, redacts sensitive files/tokens,
chunks large source code preserving line mapping, and produces bounded
AnalysisContext instances for each specialized agent.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.agents.base import AnalysisContext
from app.analysis.chunker import chunk_files
from app.analysis.file_selector import FileSelector
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review

logger = logging.getLogger("ai_code_reviewer.context_builder")

# Sensitive file path patterns to never send raw to LLMs
SENSITIVE_FILE_PATTERNS = re.compile(
    r"(\.env($|\.)|credentials\.json|id_rsa|\.pem$|\.key$|service-account.*\.json)",
    re.IGNORECASE,
)

# Inline credential masking
AUTH_HEADER_PATTERN = re.compile(r"(Authorization:\s*Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE)
GITHUB_TOKEN_PATTERN = re.compile(r"\b(ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82})\b")


def sanitize_file_content(path: str, content: str) -> str:
    """
    Ensure sensitive files and raw secrets are never passed into LLM prompt contexts.
    """
    if SENSITIVE_FILE_PATTERNS.search(path):
        return (
            f"# [SECURITY NOTE: Contents of '{path}' were redacted prior to LLM analysis "
            f"to protect sensitive credentials and environment configuration.]\n"
        )

    # Redact any obvious tokens or authorization headers embedded in code
    sanitized = AUTH_HEADER_PATTERN.sub(r"\1[REDACTED_AUTH_TOKEN]", content)
    sanitized = GITHUB_TOKEN_PATTERN.sub("[REDACTED_GH_TOKEN]", sanitized)
    return sanitized


class ContextBuilder:
    """Constructs bounded, agent-specific AnalysisContext instances."""

    def __init__(self) -> None:
        self.file_selector = FileSelector()

    def _parse_snapshot_json(self, raw_str: Optional[str], default_val: Any) -> Any:
        if not raw_str:
            return default_val
        try:
            return json.loads(raw_str)
        except Exception:
            return default_val

    def _base_context_kwargs(
        self,
        review: Review,
        snapshot: RepositorySnapshot,
        all_files: Dict[str, str],
    ) -> Dict[str, Any]:
        """Extract parsed snapshot metadata and clean file contents."""
        languages = self._parse_snapshot_json(snapshot.languages, {})
        frameworks = self._parse_snapshot_json(snapshot.frameworks, [])
        dependencies = self._parse_snapshot_json(snapshot.dependencies, [])
        structure = self._parse_snapshot_json(snapshot.structure, {})

        # Safely resolve repository name without triggering SQLAlchemy lazy-load greenlet error
        repo = review.__dict__.get("repository") or getattr(review, "repository", None)
        repo_name = getattr(repo, "full_name", None) or "repository"

        statistics = {
            "total_files": snapshot.total_files or len(all_files),
            "source_files": snapshot.source_files or 0,
            "test_files": snapshot.test_files or 0,
            "config_files": snapshot.config_files or 0,
            "total_lines": snapshot.total_lines or 0,
        }

        # Sanitize all file contents before any agent can access them
        sanitized_files = {
            path: sanitize_file_content(path, content)
            for path, content in all_files.items()
        }

        return {
            "review_id": review.id,
            "repository_id": review.repository_id,
            "repository_name": repo_name,
            "commit_sha": review.commit_sha,
            "branch": review.branch,
            "languages": languages,
            "frameworks": frameworks,
            "dependencies": dependencies,
            "structure": structure,
            "statistics": statistics,
            "file_tree": list(all_files.keys()),
            "_clean_files": sanitized_files,
        }

    def build_understanding_context(
        self,
        review: Review,
        snapshot: RepositorySnapshot,
        all_files: Dict[str, str],
        max_tokens: int = 25000,
    ) -> AnalysisContext:
        """Context for Code Understanding Agent."""
        kwargs = self._base_context_kwargs(review, snapshot, all_files)
        clean_files = kwargs.pop("_clean_files")

        entry_points = kwargs["structure"].get("entry_points", [])
        selected = self.file_selector.select_for_understanding(
            clean_files, entry_points=entry_points, max_tokens=max_tokens
        )
        chunks = chunk_files(selected, max_lines=150, overlap=15)

        return AnalysisContext(
            agent_type="code_understanding",
            selected_files=selected,
            chunks=chunks,
            **kwargs,
        )

    def build_code_review_context(
        self,
        review: Review,
        snapshot: RepositorySnapshot,
        all_files: Dict[str, str],
        max_tokens: int = 30000,
    ) -> AnalysisContext:
        """Context for Code Review Agent."""
        return self.build_code_quality_context(
            review=review, snapshot=snapshot, all_files=all_files, max_tokens=max_tokens
        )

    def build_code_quality_context(
        self,
        review: Review,
        snapshot: RepositorySnapshot,
        all_files: Dict[str, str],
        max_tokens: int = 30000,
    ) -> AnalysisContext:
        """Context for Code Quality Agent."""
        kwargs = self._base_context_kwargs(review, snapshot, all_files)
        clean_files = kwargs.pop("_clean_files")

        selected = self.file_selector.select_for_code_review(
            clean_files, max_tokens=max_tokens
        )
        chunks = chunk_files(selected, max_lines=150, overlap=20)

        return AnalysisContext(
            agent_type="code_quality",
            selected_files=selected,
            chunks=chunks,
            **kwargs,
        )

    def build_security_context(
        self,
        review: Review,
        snapshot: RepositorySnapshot,
        all_files: Dict[str, str],
        static_findings: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 30000,
    ) -> AnalysisContext:
        """Context for Security Agent."""
        return self.build_security_detection_context(
            review=review,
            snapshot=snapshot,
            all_files=all_files,
            static_findings=static_findings,
            max_tokens=max_tokens,
        )

    def build_security_detection_context(
        self,
        review: Review,
        snapshot: RepositorySnapshot,
        all_files: Dict[str, str],
        static_findings: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 30000,
    ) -> AnalysisContext:
        """Context for Security Detection Agent."""
        kwargs = self._base_context_kwargs(review, snapshot, all_files)
        clean_files = kwargs.pop("_clean_files")

        selected = self.file_selector.select_for_security(
            clean_files, max_tokens=max_tokens
        )
        chunks = chunk_files(selected, max_lines=150, overlap=20)

        return AnalysisContext(
            agent_type="security_agent",
            selected_files=selected,
            chunks=chunks,
            static_findings=static_findings or [],
            **kwargs,
        )
