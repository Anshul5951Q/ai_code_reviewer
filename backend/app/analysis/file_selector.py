"""
Agent-specific file selection and context budgeting.

Filters and prioritizes repository files to construct bounded, task-specific
contexts for each agent without exceeding token limits or leaking unnecessary files.
"""
from __future__ import annotations

import re
from typing import Dict, List, Set


def estimate_tokens(text: str) -> int:
    """Approximate token count based on character length (~4 chars per token)."""
    return max(1, len(text) // 4)


class FileSelector:
    """Selects and prioritizes files based on agent specialization."""

    SECURITY_KEYWORDS = re.compile(
        r"(auth|login|session|jwt|token|passwd|password|credential|secret|"
        r"api|route|endpoint|handler|controller|service|"
        r"db|database|query|sql|repo|model|migration|"
        r"exec|spawn|subprocess|shell|command|system|"
        r"upload|download|file|path|fs|dir|storage|"
        r"middleware|cors|guard|crypto|hash|ssl|cert|oauth)",
        re.IGNORECASE,
    )

    CONFIG_MANIFESTS = {
        "package.json", "requirements.txt", "pyproject.toml", "go.mod",
        "Cargo.toml", "pom.xml", "build.gradle", "composer.json",
        "Gemfile", "tsconfig.json", "Dockerfile", "docker-compose.yml",
    }

    ENTRY_POINT_NAMES = {
        "main.py", "app.py", "server.py", "index.ts", "index.js",
        "main.ts", "main.go", "app.ts", "server.ts", "Main.java",
    }

    def select_for_understanding(
        self,
        files: Dict[str, str],
        entry_points: List[str] | None = None,
        max_tokens: int = 25000,
    ) -> Dict[str, str]:
        """
        Select files relevant to overall architecture and project understanding.

        Prioritizes:
        1. Entry points
        2. Package & configuration manifests
        3. Top-level architectural files / index files / routers
        """
        eps: Set[str] = set(entry_points or [])
        selected: Dict[str, str] = {}
        total_tokens = 0

        # Score files by architectural relevance
        scored: List[tuple[int, str, str]] = []
        for path, content in files.items():
            score = 0
            filename = path.split("/")[-1]
            lower_path = path.lower()

            if path in eps or filename in self.ENTRY_POINT_NAMES:
                score += 100
            if filename in self.CONFIG_MANIFESTS:
                score += 80
            if any(k in lower_path for k in ("config", "setting", "init", "route", "router")):
                score += 40
            if any(k in lower_path for k in ("app", "server", "core", "schema", "model")):
                score += 20

            # Penalize tests or deeply nested files for high-level understanding
            if "test" in lower_path or "spec" in lower_path:
                score -= 30

            scored.append((score, path, content))

        scored.sort(key=lambda x: x[0], reverse=True)

        for _, path, content in scored:
            cost = estimate_tokens(content)
            if total_tokens + cost <= max_tokens or not selected:
                selected[path] = content
                total_tokens += cost
            if total_tokens >= max_tokens:
                break

        return selected

    def select_for_security(
        self,
        files: Dict[str, str],
        max_tokens: int = 30000,
    ) -> Dict[str, str]:
        """
        Select files with high security sensitivity.

        Prioritizes:
        1. Authentication / Authorization handlers
        2. Database query builders & ORM models
        3. API endpoints & routing controllers
        4. Subprocess execution & filesystem manipulation
        """
        selected: Dict[str, str] = {}
        total_tokens = 0

        scored: List[tuple[int, str, str]] = []
        for path, content in files.items():
            score = 0
            lower_path = path.lower()

            matches = len(self.SECURITY_KEYWORDS.findall(lower_path))
            score += matches * 20

            # Content-based heuristics for security hotspots
            if any(p in content for p in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "execute(")):
                score += 30
            if any(p in content for p in ("subprocess", "exec(", "system(", "shell=True")):
                score += 40
            if any(p in content for p in ("dangerouslySetInnerHTML", "innerHTML", "eval(")):
                score += 40
            if any(p in content for p in ("password", "secret", "token", "jwt", "api_key")):
                score += 25
            if any(p in content for p in ("open(", "readFile", "writeFile", "unlink")):
                score += 20

            # Exclude tests from primary security scan to reduce noise
            if "test" in lower_path or "spec" in lower_path or "mock" in lower_path:
                score -= 50

            if score > 0:
                scored.append((score, path, content))

        scored.sort(key=lambda x: x[0], reverse=True)

        for _, path, content in scored:
            cost = estimate_tokens(content)
            if total_tokens + cost <= max_tokens or not selected:
                selected[path] = content
                total_tokens += cost
            if total_tokens >= max_tokens:
                break

        # Fallback: if no security hotspots scored, take top files
        if not selected and files:
            for path, content in list(files.items())[:5]:
                selected[path] = content

        return selected

    def select_for_code_review(
        self,
        files: Dict[str, str],
        max_tokens: int = 30000,
    ) -> Dict[str, str]:
        """
        Select files for code quality, maintainability, and code smells.

        Prioritizes:
        1. Large, complex implementation files
        2. Service layers and business logic
        3. Core utility libraries and helper modules
        """
        selected: Dict[str, str] = {}
        total_tokens = 0

        scored: List[tuple[int, str, str]] = []
        for path, content in files.items():
            score = 0
            lines = content.count("\n")
            lower_path = path.lower()

            # Larger files generally have more maintainability challenges
            score += min(lines // 10, 50)

            if any(k in lower_path for k in ("service", "manager", "handler", "util", "helper", "core")):
                score += 30

            # Include tests with moderate weight to check testing gaps/practices
            if "test" in lower_path or "spec" in lower_path:
                score += 15

            # Don't spend code review tokens on simple configs or JSON
            if path.endswith((".json", ".yml", ".yaml", ".md", ".txt")):
                score -= 40

            scored.append((score, path, content))

        scored.sort(key=lambda x: x[0], reverse=True)

        for _, path, content in scored:
            cost = estimate_tokens(content)
            if total_tokens + cost <= max_tokens or not selected:
                selected[path] = content
                total_tokens += cost
            if total_tokens >= max_tokens:
                break

        return selected
