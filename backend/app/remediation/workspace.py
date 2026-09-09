"""
Isolated temporary disk workspace for safe patch application and verification.

Ensures remediation code modifications occur strictly inside an isolated
sandbox directory and never touch production source or git repositories.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from app.remediation.patch_generator import PatchValidationError, sanitize_relative_path

logger = logging.getLogger("ai_code_reviewer.workspace")

# Base directory for isolated remediation workspaces
DEFAULT_WORKSPACE_BASE = Path(__file__).resolve().parent.parent.parent / "runtime" / "workspaces"


class IsolatedWorkspace:
    """
    Manages a sandboxed directory for applying and verifying remediation patches.

    Lifecycle:
    1. Instantiation creates `workspace_path = base / review_id / remediation_id`.
    2. `populate()` copies or writes relevant source files into the sandbox.
    3. `apply_file_content()` writes patched content with path traversal protections.
    4. `cleanup()` removes the sandbox directory and its contents.
    """

    def __init__(
        self,
        review_id: str,
        remediation_id: str,
        base_dir: Optional[Path] = None,
    ) -> None:
        self.review_id = review_id
        self.remediation_id = remediation_id
        base = base_dir or DEFAULT_WORKSPACE_BASE
        self.workspace_path: Path = base / review_id / remediation_id
        self._is_active = False

    def __enter__(self) -> "IsolatedWorkspace":
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()

    def create(self) -> Path:
        """Create the isolated workspace directory."""
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self._is_active = True
        logger.debug(f"Created isolated workspace at: {self.workspace_path}")
        return self.workspace_path

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """
        Resolve relative path inside workspace and strictly enforce that it does not escape.
        """
        clean_rel = sanitize_relative_path(relative_path)
        resolved = (self.workspace_path / clean_rel).resolve()

        # Enforce that resolved path starts with workspace_path
        ws_resolved = self.workspace_path.resolve()
        if not str(resolved).startswith(str(ws_resolved)):
            raise PatchValidationError(
                f"Path resolution escaped isolated workspace: '{relative_path}'"
            )

        return resolved

    def populate(self, files: Dict[str, str]) -> None:
        """
        Write provided file paths and string contents into the workspace.
        """
        if not self._is_active:
            self.create()

        for rel_path, content in files.items():
            target_path = self._resolve_safe_path(rel_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

    def write_file(self, relative_path: str, content: str) -> None:
        """Write or overwrite an individual file inside the workspace."""
        if not self._is_active:
            self.create()

        target_path = self._resolve_safe_path(relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")

    def read_file(self, relative_path: str) -> str:
        """Read content of a file within the workspace."""
        target_path = self._resolve_safe_path(relative_path)
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"File '{relative_path}' does not exist in workspace.")
        return target_path.read_text(encoding="utf-8")

    def file_exists(self, relative_path: str) -> bool:
        """Check whether a file exists in the workspace."""
        try:
            target_path = self._resolve_safe_path(relative_path)
            return target_path.exists() and target_path.is_file()
        except PatchValidationError:
            return False

    def list_files(self) -> List[str]:
        """List all relative file paths inside the workspace."""
        if not self.workspace_path.exists():
            return []

        rel_paths: List[str] = []
        ws_resolved = self.workspace_path.resolve()
        for root, _, files in os.walk(self.workspace_path):
            for file in files:
                full_path = Path(root) / file
                rel = full_path.relative_to(ws_resolved).as_posix()
                rel_paths.append(rel)
        return sorted(rel_paths)

    def cleanup(self) -> None:
        """Remove the isolated workspace directory and all contained files."""
        if self.workspace_path.exists():
            try:
                shutil.rmtree(self.workspace_path, ignore_errors=True)
                logger.debug(f"Cleaned up isolated workspace: {self.workspace_path}")
            except Exception as exc:
                logger.warning(f"Failed to cleanup workspace {self.workspace_path}: {exc}")
        self._is_active = False
