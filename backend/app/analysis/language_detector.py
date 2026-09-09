"""
Deterministic language detection based on file extensions.

No LLM, no external calls. Pure extension → language mapping.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List


# ---------------------------------------------------------------------------
# Extension → Language mapping
# ---------------------------------------------------------------------------
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    # TypeScript / JavaScript
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    # Python
    ".py": "Python",
    ".pyi": "Python",
    # Java
    ".java": "Java",
    # Go
    ".go": "Go",
    # Rust
    ".rs": "Rust",
    # C / C++
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    # C#
    ".cs": "C#",
    # PHP
    ".php": "PHP",
    # Ruby
    ".rb": "Ruby",
    # Swift
    ".swift": "Swift",
    # Kotlin
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    # Scala
    ".scala": "Scala",
    # SQL
    ".sql": "SQL",
    # Shell
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    # R
    ".r": "R",
    ".R": "R",
    # Dart
    ".dart": "Dart",
    # Lua
    ".lua": "Lua",
    # Elixir
    ".ex": "Elixir",
    ".exs": "Elixir",
    # Clojure
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
    # Haskell
    ".hs": "Haskell",
    ".lhs": "Haskell",
    # OCaml
    ".ml": "OCaml",
    ".mli": "OCaml",
    # Vue
    ".vue": "Vue",
    # Svelte
    ".svelte": "Svelte",
    # Elm
    ".elm": "Elm",
    # Terraform
    ".tf": "Terraform",
    ".tfvars": "Terraform",
    # YAML / JSON / TOML (counted separately as "data")
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    # HTML / CSS
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".sass": "CSS",
    ".less": "CSS",
    # Markdown
    ".md": "Markdown",
    ".rst": "Markdown",
    # XML
    ".xml": "XML",
}


@dataclass
class LanguageStat:
    """Statistics for a detected language."""
    language: str
    files: int = 0
    percentage: float = 0.0

    def to_dict(self) -> dict:
        return {"files": self.files, "percentage": round(self.percentage, 1)}


def detect_languages(file_paths: List[str]) -> Dict[str, LanguageStat]:
    """
    Detect languages from a list of file paths.

    Parameters
    ----------
    file_paths:
        List of relative file paths from the repository tree.

    Returns
    -------
    dict mapping language name → LanguageStat, sorted by file count descending.
    Only languages with at least 1 file are returned.
    """
    counts: Dict[str, int] = {}

    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        lang = EXTENSION_TO_LANGUAGE.get(ext)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1

    total = sum(counts.values())
    if total == 0:
        return {}

    result: Dict[str, LanguageStat] = {}
    for lang, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        result[lang] = LanguageStat(
            language=lang,
            files=count,
            percentage=round((count / total) * 100, 1),
        )

    return result
