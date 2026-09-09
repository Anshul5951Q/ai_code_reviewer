"""
File chunking utility.

Divides large source files into bounded chunks with overlapping lines to preserve
semantic context around line boundaries. Never loses source line mapping.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class FileChunk:
    """Represents a bounded slice of a source file with strict line number mapping."""

    file_path: str
    start_line: int  # 1-indexed, inclusive
    end_line: int    # 1-indexed, inclusive
    chunk_index: int
    content: str
    total_lines: int

    def to_dict(self) -> dict:
        return {
            "file": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_index": self.chunk_index,
            "total_lines": self.total_lines,
        }


def chunk_file(
    file_path: str,
    content: str,
    max_lines: int = 150,
    overlap: int = 20,
) -> List[FileChunk]:
    """
    Split a single file into bounded line chunks.

    If file is empty or shorter than max_lines, returns a single chunk.
    Line numbers are 1-indexed and exact.
    """
    if not content:
        return [
            FileChunk(
                file_path=file_path,
                start_line=1,
                end_line=1,
                chunk_index=0,
                content="",
                total_lines=0,
            )
        ]

    lines = content.splitlines(keepends=True)
    total_lines = len(lines)

    if total_lines <= max_lines:
        return [
            FileChunk(
                file_path=file_path,
                start_line=1,
                end_line=total_lines,
                chunk_index=0,
                content=content,
                total_lines=total_lines,
            )
        ]

    chunks: List[FileChunk] = []
    chunk_index = 0
    start_idx = 0

    while start_idx < total_lines:
        end_idx = min(start_idx + max_lines, total_lines)
        chunk_lines = lines[start_idx:end_idx]
        chunk_content = "".join(chunk_lines)

        chunks.append(
            FileChunk(
                file_path=file_path,
                start_line=start_idx + 1,  # 1-indexed
                end_line=end_idx,          # 1-indexed inclusive
                chunk_index=chunk_index,
                content=chunk_content,
                total_lines=total_lines,
            )
        )
        chunk_index += 1

        if end_idx >= total_lines:
            break

        # Move forward, stepping back by overlap
        step = max(max_lines - overlap, 1)
        start_idx += step

    return chunks


def chunk_files(
    files: Dict[str, str],
    max_lines: int = 150,
    overlap: int = 20,
) -> List[FileChunk]:
    """Chunk multiple files preserving line mapping for each."""
    all_chunks: List[FileChunk] = []
    for file_path, content in files.items():
        all_chunks.extend(
            chunk_file(file_path, content, max_lines=max_lines, overlap=overlap)
        )
    return all_chunks
