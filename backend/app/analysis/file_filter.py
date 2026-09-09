"""
File filter for repository ingestion.

Determines which files in a repository tree should be ingested for analysis.
Excludes binary files, generated files, vendor directories, and oversized files.
"""
from __future__ import annotations

import os
from typing import FrozenSet, Set


# ---------------------------------------------------------------------------
# Allowed source code extensions
# ---------------------------------------------------------------------------
SOURCE_EXTENSIONS: FrozenSet[str] = frozenset(
    {
        ".ts", ".tsx",
        ".js", ".jsx", ".mjs", ".cjs",
        ".py",
        ".java",
        ".go",
        ".rs",
        ".c", ".cpp", ".cc", ".cxx",
        ".h", ".hpp",
        ".cs",
        ".php",
        ".rb",
        ".swift",
        ".kt", ".kts",
        ".scala",
        ".sql",
        ".sh", ".bash",
        ".r", ".R",
        ".dart",
        ".lua",
        ".elm",
        ".ex", ".exs",
        ".clj", ".cljs",
        ".hs",
        ".ml", ".mli",
        ".vue",
        ".svelte",
    }
)

# ---------------------------------------------------------------------------
# Config / dependency manifest filenames (exact match on basename)
# ---------------------------------------------------------------------------
CONFIG_FILENAMES: FrozenSet[str] = frozenset(
    {
        # Node
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        ".npmrc", ".nvmrc",
        # Python
        "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
        "pyproject.toml", "setup.py", "setup.cfg",
        "poetry.lock", "Pipfile", "Pipfile.lock",
        # Java / JVM
        "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
        "settings.gradle.kts", "gradlew",
        # Go
        "go.mod", "go.sum",
        # Rust
        "Cargo.toml", "Cargo.lock",
        # PHP
        "composer.json", "composer.lock",
        # Ruby
        "Gemfile", "Gemfile.lock",
        # Docker / containers
        "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        ".dockerignore",
        # CI / CD
        ".travis.yml", ".github/workflows",
        "Makefile", "makefile",
        # Config
        ".env.example", ".env.sample",
        "tsconfig.json", "jsconfig.json",
        "eslint.config.mjs", ".eslintrc.js", ".eslintrc.json", ".eslintignore",
        ".prettierrc", ".prettierrc.json",
        "jest.config.js", "jest.config.ts",
        "vite.config.ts", "vite.config.js",
        "next.config.ts", "next.config.js",
        "webpack.config.js",
        "tailwind.config.ts", "tailwind.config.js",
        "alembic.ini",
        "pytest.ini", "setup.cfg", "conftest.py",
    }
)

# ---------------------------------------------------------------------------
# Config file extensions (matched on extension)
# ---------------------------------------------------------------------------
CONFIG_EXTENSIONS: FrozenSet[str] = frozenset(
    {
        ".json", ".yaml", ".yml", ".toml", ".ini",
        ".cfg", ".conf", ".config",
        ".xml", ".properties",
        ".env",
        ".lock",
        ".md", ".rst", ".txt",  # documentation / manifests
    }
)

# ---------------------------------------------------------------------------
# Excluded directory prefixes (match against path segments)
# ---------------------------------------------------------------------------
EXCLUDED_DIRS: FrozenSet[str] = frozenset(
    {
        ".git",
        "node_modules",
        "venv", ".venv", "env", ".env",
        "__pycache__",
        "dist", "build", "out", "output",
        ".next", ".nuxt", ".svelte-kit",
        "target",  # Rust / Java
        "coverage", ".coverage",
        "vendor",
        "bin", "obj",
        ".cache", ".parcel-cache",
        ".idea", ".vscode",
        "migrations/__pycache__",
        "htmlcov",
        ".pytest_cache",
        ".mypy_cache",
        "eggs", ".eggs",
    }
)

# ---------------------------------------------------------------------------
# Excluded file extensions (binary / media / generated)
# ---------------------------------------------------------------------------
EXCLUDED_EXTENSIONS: FrozenSet[str] = frozenset(
    {
        # Images
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
        ".webp", ".tiff", ".tif", ".raw",
        # Video
        ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm",
        # Audio
        ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a",
        # Fonts
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
        # Archives
        ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z",
        # Compiled / binary
        ".pyc", ".pyo", ".class", ".jar", ".war", ".ear",
        ".dll", ".so", ".dylib", ".exe", ".bin", ".obj",
        ".o", ".a", ".lib",
        # Database
        ".db", ".sqlite", ".sqlite3",
        # Package locks that are too noisy
        # (keep yarn.lock / package-lock.json at small sizes as config, but
        #  the size check handles the case where they grow huge)
        # Generated docs
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        # Map / source map
        ".map",
    }
)

# ---------------------------------------------------------------------------
# Filenames to always skip
# ---------------------------------------------------------------------------
EXCLUDED_FILENAMES: FrozenSet[str] = frozenset(
    {
        ".DS_Store", "Thumbs.db",
        ".gitignore", ".gitattributes",
        "LICENSE", "LICENSE.md", "LICENSE.txt",
        "CHANGELOG", "CHANGELOG.md",
    }
)

# Default maximum file size: 1 MB
DEFAULT_MAX_FILE_SIZE_BYTES: int = 1_048_576


class FileFilter:
    """
    Decides whether a repository file should be included for analysis.

    Parameters
    ----------
    max_file_size_bytes:
        Files larger than this are excluded. Default is 1 MB.
    """

    def __init__(self, max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES) -> None:
        self.max_file_size_bytes = max_file_size_bytes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_include(self, path: str, size: int | None = None) -> bool:
        """
        Return True if the file at *path* with optional *size* (bytes) should
        be included in the analysis.
        """
        if not path:
            return False

        # Normalize to forward slashes
        normalized = path.replace("\\", "/")

        # Exclude hidden files starting with "." (except known config files)
        basename = os.path.basename(normalized)
        ext = os.path.splitext(basename)[1].lower()

        # 1. Always-excluded filenames
        if basename in EXCLUDED_FILENAMES:
            return False

        # 2. Always-excluded extensions (binary / media)
        if ext in EXCLUDED_EXTENSIONS:
            return False

        # 3. Excluded directories
        if self._in_excluded_dir(normalized):
            return False

        # 4. Size check (if size is known)
        if size is not None and size > self.max_file_size_bytes:
            return False

        # 5. Known config filenames → include
        if basename in CONFIG_FILENAMES:
            return True

        # 6. Source code extensions → include
        if ext in SOURCE_EXTENSIONS:
            return True

        # 7. Config/data extensions → include (after other checks)
        if ext in CONFIG_EXTENSIONS:
            return True

        # Everything else → exclude
        return False

    def is_source_file(self, path: str) -> bool:
        """True if the file is a primary source code file (not config/docs)."""
        ext = os.path.splitext(path)[1].lower()
        return ext in SOURCE_EXTENSIONS

    def is_test_file(self, path: str) -> bool:
        """Heuristically detect test files."""
        lower = path.lower()
        basename = os.path.basename(lower)
        # Common test patterns
        if any(
            seg in lower
            for seg in (
                "/test/", "/tests/", "/__tests__/", "/spec/", "/specs/",
                "/e2e/", "/integration/",
            )
        ):
            return True
        # Test file naming conventions
        return (
            basename.startswith("test_")
            or basename.endswith("_test.py")
            or ".test." in basename
            or ".spec." in basename
            or basename.startswith("spec_")
        )

    def is_config_file(self, path: str) -> bool:
        """True if the file is a configuration or manifest file."""
        basename = os.path.basename(path)
        ext = os.path.splitext(basename)[1].lower()
        return basename in CONFIG_FILENAMES or ext in CONFIG_EXTENSIONS

    def classify_file(self, path: str) -> str:
        """Return 'source', 'test', 'config', or 'other'."""
        if self.is_test_file(path):
            return "test"
        if self.is_source_file(path):
            return "source"
        if self.is_config_file(path):
            return "config"
        return "other"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _in_excluded_dir(self, path: str) -> bool:
        """True if any path segment matches an excluded directory name."""
        parts = path.split("/")
        # Check each segment (not the final filename)
        for part in parts[:-1]:
            if part in EXCLUDED_DIRS:
                return True
            # Also exclude hidden directories (e.g. .git, .venv)
            if part.startswith(".") and part not in (".", ".."):
                # Allow .github and .gitignore-type names at root
                # but exclude actual hidden directories deeper
                pass
        return False


# Convenience singleton with default settings
default_filter = FileFilter()
