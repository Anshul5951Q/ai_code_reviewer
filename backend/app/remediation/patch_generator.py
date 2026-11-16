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


class PatchGenerator:
    """
    Dedicated Patch Generation Service.
    Produces parseable unified diffs strictly grounded against an existing repository snapshot.
    """

    PROTECTED_FILE_PATTERNS = [
        re.compile(r"(?:^|/)\.env(?:$|\.)", re.IGNORECASE),
        re.compile(r"(?:^|/)\.git(?:$|/)", re.IGNORECASE),
        re.compile(r"\.(?:pem|key|crt)$", re.IGNORECASE),
        re.compile(r"id_rsa", re.IGNORECASE),
    ]

    def __init__(self, max_files: int = 5, max_lines: int = 150, max_size_bytes: int = 50000) -> None:
        self.max_files = max_files
        self.max_lines = max_lines
        self.max_size_bytes = max_size_bytes

    def is_protected_file(self, file_path: str) -> bool:
        clean = file_path.replace("\\", "/").strip()
        return any(pat.search(clean) for pat in self.PROTECTED_FILE_PATTERNS)

    def generate_patch(
        self,
        snapshot_files: Dict[str, str],
        changes: List[Any],
        patch_version: int = 1,
    ) -> Tuple[str, List[str], Dict[str, str]]:
        """
        Apply a series of code changes against snapshot files and generate standard unified diff.

        Returns:
            Tuple of (unified_diff_string, modified_files_list, modified_contents_dict).
        Raises:
            PatchValidationError on safety or applicability failure.
        """
        if not changes:
            raise PatchValidationError("No code changes provided to generate patch.")

        modified_files: List[str] = []
        modified_contents: Dict[str, str] = {}
        diff_chunks: List[str] = []

        # Group changes by file
        from collections import defaultdict
        file_changes = defaultdict(list)
        for c in changes:
            fp = getattr(c, "file_path", None) or (c.get("file_path") if isinstance(c, dict) else None)
            if not fp:
                raise PatchValidationError("Code change missing required 'file_path'.")
            clean_p = sanitize_relative_path(fp)
            file_changes[clean_p].append(c)

        if len(file_changes) > self.max_files:
            raise PatchValidationError(
                f"Patch targets {len(file_changes)} files, exceeding limit of {self.max_files}."
            )

        for file_path, f_changes in file_changes.items():
            if self.is_protected_file(file_path):
                raise PatchValidationError(f"Modification of protected file '{file_path}' is strictly forbidden.")

            # Validate target file exists in snapshot
            if file_path not in snapshot_files:
                # Attempt suffix match
                matched = [k for k in snapshot_files if k.endswith(f"/{file_path}") or k == file_path]
                if not matched:
                    raise PatchValidationError(f"Target file '{file_path}' does not exist in repository snapshot.")
                snapshot_key = matched[0]
            else:
                snapshot_key = file_path

            original_content = snapshot_files[snapshot_key]
            curr_content = original_content

            for change in f_changes:
                start_l = getattr(change, "start_line", None) or (change.get("start_line") if isinstance(change, dict) else 1)
                end_l = getattr(change, "end_line", None) or (change.get("end_line") if isinstance(change, dict) else start_l)
                orig_code = getattr(change, "original_code", None) or (change.get("original_code") if isinstance(change, dict) else "")
                repl_code = getattr(change, "replacement_code", None) or (change.get("replacement_code") if isinstance(change, dict) else "")

                # Stale patch verification
                norm_orig = orig_code.strip()
                if norm_orig and norm_orig not in curr_content:
                    lines = curr_content.splitlines()
                    s_idx = max(1, start_l) - 1
                    e_idx = min(len(lines), end_l)
                    target_chunk = "\n".join(lines[s_idx:e_idx]).strip()
                    if norm_orig not in target_chunk and target_chunk not in norm_orig:
                        raise PatchValidationError(
                            f"Stale patch detected for '{file_path}': expected code snippet not found at lines {start_l}-{end_l}."
                        )

                curr_content = apply_code_change(
                    original_content=curr_content,
                    start_line=start_l,
                    end_line=end_l,
                    original_code=orig_code,
                    replacement_code=repl_code,
                )

            diff = generate_unified_diff(file_path, original_content, curr_content)
            if diff:
                diff_chunks.append(diff)
                modified_files.append(file_path)
                modified_contents[file_path] = curr_content

        unified_diff_str = "\n".join(diff_chunks)
        validate_patch_safety(
            file_paths=modified_files,
            diff_text=unified_diff_str,
            max_files=self.max_files,
            max_lines=self.max_lines,
            max_size_bytes=self.max_size_bytes,
        )

        return unified_diff_str, modified_files, modified_contents
