"""
Local Analysis Workspace and File Cache.

Stores downloaded repository source files on disk per review session.
Prevents redundant GitHub API fetches, eliminates rate-limit vulnerability,
and ensures IngestionPipeline and AnalysisOrchestrator inspect identical files.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("ai_code_reviewer.analysis_workspace")

# Root directory for cached repository review files
ANALYSIS_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent / "runtime" / "workspaces" / "reviews"


class AnalysisWorkspace:
    """Manages the disk storage of source code files for a review."""

    def __init__(self, review_id: str, root_dir: Optional[Path] = None) -> None:
        self.review_id = review_id
        base = root_dir or ANALYSIS_WORKSPACE_ROOT
        self.workspace_dir: Path = base / review_id / "source"

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """Sanitize and resolve a relative file path inside the workspace."""
        clean_rel = relative_path.strip().replace("\\", "/")
        if ".." in clean_rel.split("/"):
            raise ValueError(f"Path traversal detected: '{relative_path}' escapes workspace.")
        target = (self.workspace_dir / clean_rel).resolve()
        try:
            target.relative_to(self.workspace_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"Path traversal detected: '{relative_path}' escapes workspace.") from exc
        return target

    def save_files(self, files: Dict[str, str]) -> int:
        """Write file contents to disk inside the review workspace."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for rel_path, content in files.items():
            if content is None:
                continue
            target_file = self._resolve_safe_path(rel_path)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(content, encoding="utf-8", errors="replace")
            count += 1
        logger.debug(f"Saved {count} files to analysis workspace for review {self.review_id}")
        return count

    def load_files(self) -> Dict[str, str]:
        """Read all saved files from the workspace back into a dictionary."""
        if not self.workspace_dir.exists():
            return {}

        loaded: Dict[str, str] = {}
        for file_path in self.workspace_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(self.workspace_dir).as_posix()
                try:
                    loaded[rel_path] = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception as exc:
                    logger.warning(f"Could not read cached file {rel_path}: {exc}")
        return loaded

    def has_files(self) -> bool:
        """Check if workspace exists and contains at least one file."""
        return self.workspace_dir.exists() and any(self.workspace_dir.iterdir())

    def get_file(self, relative_path: str) -> Optional[str]:
        """Read a single file from the workspace."""
        target = self._resolve_safe_path(relative_path)
        if target.is_file():
            return target.read_text(encoding="utf-8", errors="replace")
        return None

    def cleanup(self) -> None:
        """Remove workspace directory and cached files."""
        if self.workspace_dir.parent.exists():
            shutil.rmtree(self.workspace_dir.parent, ignore_errors=True)
