"""
Unified diff generator, safety validator, and line-level code patch applier.

Produces parseable unified diffs and strictly validates that changes
cannot escape isolated workspaces or exceed safety constraints.
"""
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


class PatchValidationError(Exception):
    """Raised when a patch fails safety or validation criteria."""
    pass


@dataclass
class CodeChangeChunk:
    """Individual file modification instruction."""

    file_path: str
    start_line: int
    end_line: int
    original_code: str
    replacement_code: str


def sanitize_relative_path(path_str: str) -> str:
    """
    Ensure the path is strictly relative and does not attempt path traversal
    or escape the workspace root.
    """
    clean = path_str.replace("\\", "/").strip()
    # Strip any leading slash or drive letter
    clean = re.sub(r"^[a-zA-Z]:[/]?", "", clean)
    clean = clean.lstrip("/")

    parts = [p for p in clean.split("/") if p and p != "."]
    if not parts or ".." in parts:
        raise PatchValidationError(f"Invalid or escaping file path: '{path_str}'")

    return "/".join(parts)


def validate_patch_safety(
    file_paths: List[str],
    diff_text: str,
    max_files: int = 5,
    max_lines: int = 150,
    max_size_bytes: int = 50000,
) -> bool:
    """
    Validate that patch respects all security and operational boundaries.

    Checks:
    - No path traversal or absolute paths.
    - Number of modified files <= max_files.
    - Total changed lines (+/-) <= max_lines.
    - Patch payload byte size <= max_size_bytes.
    """
    # 1. Size limit
    diff_bytes = len(diff_text.encode("utf-8"))
    if diff_bytes > max_size_bytes:
        raise PatchValidationError(
            f"Patch size ({diff_bytes} bytes) exceeds limit of {max_size_bytes} bytes."
        )

    # 2. File count limit
    if len(file_paths) > max_files:
        raise PatchValidationError(
            f"Patch modifies {len(file_paths)} files, exceeding limit of {max_files}."
        )

    # 3. Path safety
    for p in file_paths:
        sanitize_relative_path(p)

    # 4. Changed lines limit
    added_lines = 0
    removed_lines = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_lines += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed_lines += 1

    total_changed = added_lines + removed_lines
    if total_changed > max_lines:
        raise PatchValidationError(
            f"Patch modifies {total_changed} lines (+{added_lines}/-{removed_lines}), "
            f"exceeding limit of {max_lines} lines."
        )

    return True


def apply_code_change(
    original_content: str,
    start_line: int,
    end_line: int,
    original_code: str,
    replacement_code: str,
) -> str:
    """
    Apply replacement code to original file content at [start_line, end_line] (1-indexed).

    If line numbers match exactly, replaces those lines.
    If line numbers are slightly shifted, attempts content-based location.
    """
    # Normalize line endings to \n
    lines = original_content.replace("\r\n", "\n").split("\n")
    total_lines = len(lines)

    # Clamp line numbers
    s_idx = max(1, start_line) - 1
    e_idx = min(total_lines, end_line)

    orig_target_block = "\n".join(lines[s_idx:e_idx])
    norm_expected = original_code.strip()
    norm_target = orig_target_block.strip()

    # If exact range content matches or is compatible
    if not norm_expected or norm_target == norm_expected or norm_expected in norm_target:
        new_lines = (
            lines[:s_idx]
            + replacement_code.splitlines()
            + lines[e_idx:]
        )
        return "\n".join(new_lines)

    # Fallback: search for original_code substring in the file
    content_str = "\n".join(lines)
    if norm_expected in content_str:
        # Direct replacement of unique substring
        occurrences = content_str.count(norm_expected)
        if occurrences == 1:
            return content_str.replace(norm_expected, replacement_code.strip(), 1)

    # If lines within bounds, apply by line numbers
    new_lines = lines[:s_idx] + replacement_code.splitlines() + lines[e_idx:]
    return "\n".join(new_lines)


def generate_unified_diff(
    file_path: str,
    original_content: str,
    modified_content: str,
) -> str:
    """
    Generate standard unified diff format between original and modified file contents.
    """
    clean_path = sanitize_relative_path(file_path)
    orig_lines = original_content.replace("\r\n", "\n").splitlines(keepends=True)
    mod_lines = modified_content.replace("\r\n", "\n").splitlines(keepends=True)

    # Ensure trailing newlines for diff consistency
    if orig_lines and not orig_lines[-1].endswith("\n"):
        orig_lines[-1] += "\n"
    if mod_lines and not mod_lines[-1].endswith("\n"):
        mod_lines[-1] += "\n"

    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{clean_path}",
        tofile=f"b/{clean_path}",
        lineterm="\n",
    )
    return "".join(diff)
