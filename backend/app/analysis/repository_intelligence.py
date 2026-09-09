"""
Repository intelligence module.

Aggregates file metadata, language statistics, and structural patterns
into a structured RepositoryIntelligence object.
No LLM calls — purely deterministic.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.analysis.dependency_analyzer import Dependency
from app.analysis.file_filter import FileFilter
from app.analysis.language_detector import LanguageStat


# ---------------------------------------------------------------------------
# Framework detection signatures
# ---------------------------------------------------------------------------

FRAMEWORK_INDICATORS: Dict[str, List[str]] = {
    # Frontend
    "React": ["react", "@types/react"],
    "Next.js": ["next"],
    "Vue": ["vue", "@vue/core"],
    "Nuxt": ["nuxt"],
    "Angular": ["@angular/core"],
    "Svelte": ["svelte", "@sveltejs/kit"],
    "Remix": ["@remix-run/react"],
    # Backend Python
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "SQLAlchemy": ["sqlalchemy"],
    # Backend Node
    "Express": ["express"],
    "NestJS": ["@nestjs/core"],
    "Fastify": ["fastify"],
    # Testing
    "Pytest": ["pytest"],
    "Jest": ["jest", "@jest/core"],
    "Vitest": ["vitest"],
    # Build tools
    "Vite": ["vite"],
    "Webpack": ["webpack"],
    # ORM / DB
    "Prisma": ["@prisma/client", "prisma"],
    "TypeORM": ["typeorm"],
    # Styling
    "Tailwind CSS": ["tailwindcss"],
    # Java
    "Spring Boot": ["spring-boot"],
    # Go
    "Gin": ["github.com/gin-gonic/gin"],
    "Echo": ["github.com/labstack/echo"],
}


@dataclass
class FileInfo:
    path: str
    size: int = 0
    lines: int = 0
    classification: str = "other"  # source | test | config | other


@dataclass
class RepositoryIntelligence:
    """Structured intelligence about a repository at a specific commit."""

    # File statistics
    total_files: int = 0
    source_files: int = 0
    test_files: int = 0
    config_files: int = 0
    total_lines: int = 0

    # Language breakdown
    languages: Dict[str, LanguageStat] = field(default_factory=dict)

    # Detected frameworks
    frameworks: List[str] = field(default_factory=list)

    # Dependency count
    total_dependencies: int = 0

    # Structural details
    largest_files: List[Dict] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    directory_structure: Dict[str, int] = field(default_factory=dict)  # dir → file count

    def to_dict(self) -> dict:
        return {
            "files": {
                "total": self.total_files,
                "source": self.source_files,
                "tests": self.test_files,
                "config": self.config_files,
            },
            "total_lines": self.total_lines,
            "languages": {
                lang: stat.to_dict() for lang, stat in self.languages.items()
            },
            "frameworks": self.frameworks,
            "total_dependencies": self.total_dependencies,
            "largest_files": self.largest_files,
            "entry_points": self.entry_points,
            "directory_structure": self.directory_structure,
        }


def _detect_frameworks(dependencies: List[Dependency]) -> List[str]:
    """Detect frameworks from dependency names."""
    dep_names_lower = {dep.name.lower() for dep in dependencies}
    detected: List[str] = []
    for framework, indicators in FRAMEWORK_INDICATORS.items():
        for indicator in indicators:
            if indicator.lower() in dep_names_lower:
                detected.append(framework)
                break
    return detected


def _detect_entry_points(file_paths: List[str]) -> List[str]:
    """Heuristically detect common entry point files."""
    common_entry_points = {
        "main.py", "app.py", "server.py", "run.py",
        "main.go",
        "main.rs",
        "main.java",
        "main.ts", "main.js",
        "index.ts", "index.js",
        "app.ts", "app.js",
        "server.ts", "server.js",
        "main.c", "main.cpp",
        "Program.cs",
    }
    return [
        p for p in file_paths
        if os.path.basename(p) in common_entry_points
    ]


def _build_directory_structure(file_paths: List[str]) -> Dict[str, int]:
    """Count files per top-level directory."""
    dir_counts: Dict[str, int] = {}
    for path in file_paths:
        parts = path.split("/")
        if len(parts) > 1:
            top_dir = parts[0]
            dir_counts[top_dir] = dir_counts.get(top_dir, 0) + 1
        else:
            dir_counts["(root)"] = dir_counts.get("(root)", 0) + 1
    return dict(sorted(dir_counts.items(), key=lambda x: x[1], reverse=True))


def analyze_repository(
    filtered_files: Dict[str, Optional[str]],
    languages: Dict[str, LanguageStat],
    dependencies: List[Dependency],
    file_filter: Optional[FileFilter] = None,
) -> RepositoryIntelligence:
    """
    Build RepositoryIntelligence from filtered files, detected languages,
    and parsed dependencies.

    Parameters
    ----------
    filtered_files:
        Dict mapping file path → file content (or None if content unavailable).
    languages:
        Language statistics from detect_languages().
    dependencies:
        Dependency list from analyze_dependencies().
    file_filter:
        Optional FileFilter instance for classification. Uses default if not provided.

    Returns
    -------
    RepositoryIntelligence
    """
    from app.analysis.file_filter import default_filter
    ff = file_filter or default_filter

    intel = RepositoryIntelligence()
    intel.languages = languages
    intel.total_dependencies = len(dependencies)
    intel.frameworks = _detect_frameworks(dependencies)

    all_paths = list(filtered_files.keys())
    intel.total_files = len(all_paths)

    # Classify files and count lines
    file_sizes: List[Dict] = []
    for path, content in filtered_files.items():
        classification = ff.classify_file(path)
        if classification == "source":
            intel.source_files += 1
        elif classification == "test":
            intel.test_files += 1
        elif classification == "config":
            intel.config_files += 1

        if content:
            lines = content.count("\n") + 1
            intel.total_lines += lines
            size = len(content.encode("utf-8", errors="replace"))
            file_sizes.append({"path": path, "size": size, "lines": lines})

    # Largest files by size (top 10)
    intel.largest_files = sorted(file_sizes, key=lambda x: x["size"], reverse=True)[:10]

    # Entry points
    intel.entry_points = _detect_entry_points(all_paths)

    # Directory structure
    intel.directory_structure = _build_directory_structure(all_paths)

    return intel
