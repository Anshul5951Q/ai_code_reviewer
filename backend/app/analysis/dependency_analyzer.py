"""
Dependency analyzer for common package manifest formats.

Parses manifest files to extract dependency information.
Does NOT perform vulnerability scanning (that belongs to a later phase).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Dependency:
    """A single dependency detected from a manifest file."""
    name: str
    version: Optional[str]
    dep_type: str  # "dependency", "dev_dependency", "peer_dependency", "optional"
    source_file: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "type": self.dep_type,
            "source_file": self.source_file,
        }


# ---------------------------------------------------------------------------
# Individual manifest parsers
# ---------------------------------------------------------------------------

def _parse_package_json(content: str, source_file: str) -> List[Dependency]:
    """Parse Node.js package.json."""
    deps: List[Dependency] = []
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return deps

    for field, dep_type in (
        ("dependencies", "dependency"),
        ("devDependencies", "dev_dependency"),
        ("peerDependencies", "peer_dependency"),
        ("optionalDependencies", "optional"),
    ):
        for name, version in data.get(field, {}).items():
            deps.append(Dependency(
                name=name,
                version=str(version) if version else None,
                dep_type=dep_type,
                source_file=source_file,
            ))
    return deps


def _parse_requirements_txt(content: str, source_file: str) -> List[Dependency]:
    """Parse Python requirements.txt."""
    deps: List[Dependency] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        # Skip comments and blank lines
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle extras: package[extra]==version
        # Strip environment markers: package>=1.0; python_version>="3.8"
        line = line.split(";")[0].strip()
        # Extract name and version
        match = re.match(
            r'^([A-Za-z0-9_\-\.\[\]]+)\s*([><=!~^]+\s*[^\s,]+)?', line
        )
        if match:
            name = match.group(1).strip()
            version = match.group(2).strip() if match.group(2) else None
            deps.append(Dependency(
                name=name,
                version=version,
                dep_type="dependency",
                source_file=source_file,
            ))
    return deps


def _parse_pyproject_toml(content: str, source_file: str) -> List[Dependency]:
    """Parse Python pyproject.toml (basic TOML parsing without external library)."""
    deps: List[Dependency] = []
    # Simple regex-based extraction for [tool.poetry.dependencies] and [project.dependencies]
    # Match dependency lines like: requests = "^2.28.0" or requests>=2.28.0
    in_deps_section = False
    section_type = "dependency"

    for line in content.splitlines():
        stripped = line.strip()

        # Detect section headers
        if re.match(r'^\[tool\.poetry\.dependencies\]', stripped):
            in_deps_section = True
            section_type = "dependency"
            continue
        elif re.match(r'^\[tool\.poetry\.dev-dependencies\]', stripped):
            in_deps_section = True
            section_type = "dev_dependency"
            continue
        elif re.match(r'^\[project\]', stripped):
            in_deps_section = False
            continue
        elif stripped.startswith("["):
            in_deps_section = False
            continue

        if in_deps_section and stripped and not stripped.startswith("#"):
            # Match: name = "version" or name = {version = "..."}
            match = re.match(r'^([a-zA-Z0-9_\-\.]+)\s*=\s*["\{](.+)', stripped)
            if match:
                name = match.group(1).strip()
                if name.lower() in ("python",):
                    continue
                version_raw = match.group(2).strip().strip('"').strip("'")
                deps.append(Dependency(
                    name=name,
                    version=version_raw[:64] if version_raw else None,
                    dep_type=section_type,
                    source_file=source_file,
                ))

    # Also handle [project] dependencies array format
    project_deps_match = re.search(
        r'\[project\][^\[]*dependencies\s*=\s*\[([^\]]+)\]',
        content,
        re.DOTALL,
    )
    if project_deps_match:
        for item in project_deps_match.group(1).splitlines():
            item = item.strip().strip('",').strip()
            if item and not item.startswith("#"):
                match = re.match(r'^([A-Za-z0-9_\-\.]+)(.*)', item)
                if match:
                    name = match.group(1)
                    version = match.group(2).strip() or None
                    deps.append(Dependency(
                        name=name,
                        version=version[:64] if version else None,
                        dep_type="dependency",
                        source_file=source_file,
                    ))

    return deps


def _parse_go_mod(content: str, source_file: str) -> List[Dependency]:
    """Parse Go go.mod."""
    deps: List[Dependency] = []
    in_require_block = False

    for line in content.splitlines():
        stripped = line.strip()

        if stripped.startswith("require ("):
            in_require_block = True
            continue
        if in_require_block and stripped == ")":
            in_require_block = False
            continue

        # Single-line require
        single = re.match(r'^require\s+(\S+)\s+(\S+)', stripped)
        if single:
            deps.append(Dependency(
                name=single.group(1),
                version=single.group(2),
                dep_type="dependency",
                source_file=source_file,
            ))
            continue

        if in_require_block and stripped and not stripped.startswith("//"):
            # Strip inline comment before splitting
            comment_pos = stripped.find("//")
            is_indirect = "// indirect" in stripped
            code_part = stripped[:comment_pos].strip() if comment_pos >= 0 else stripped
            parts = code_part.split()
            if len(parts) >= 2:
                dep_type = "dev_dependency" if is_indirect else "dependency"
                version = parts[1]
                deps.append(Dependency(
                    name=parts[0],
                    version=version,
                    dep_type=dep_type,
                    source_file=source_file,
                ))

    return deps


def _parse_cargo_toml(content: str, source_file: str) -> List[Dependency]:
    """Parse Rust Cargo.toml."""
    deps: List[Dependency] = []
    in_deps_section = False
    section_type = "dependency"

    for line in content.splitlines():
        stripped = line.strip()

        if re.match(r'^\[dependencies\]', stripped):
            in_deps_section = True
            section_type = "dependency"
            continue
        elif re.match(r'^\[dev-dependencies\]', stripped):
            in_deps_section = True
            section_type = "dev_dependency"
            continue
        elif re.match(r'^\[build-dependencies\]', stripped):
            in_deps_section = True
            section_type = "dev_dependency"
            continue
        elif stripped.startswith("["):
            in_deps_section = False
            continue

        if in_deps_section and stripped and not stripped.startswith("#"):
            match = re.match(r'^([a-zA-Z0-9_\-]+)\s*=\s*(.+)', stripped)
            if match:
                name = match.group(1)
                version_raw = match.group(2).strip().strip('"').strip("'")
                # Handle table form: { version = "1.0", features = [...] }
                if version_raw.startswith("{"):
                    ver_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', version_raw)
                    version = ver_match.group(1) if ver_match else None
                else:
                    version = version_raw[:64]
                deps.append(Dependency(
                    name=name,
                    version=version,
                    dep_type=section_type,
                    source_file=source_file,
                ))

    return deps


def _parse_pom_xml(content: str, source_file: str) -> List[Dependency]:
    """Parse Java Maven pom.xml (regex-based, no XML lib required)."""
    deps: List[Dependency] = []
    # Find all <dependency> blocks
    dep_blocks = re.findall(r'<dependency>(.*?)</dependency>', content, re.DOTALL)
    for block in dep_blocks:
        artifact_match = re.search(r'<artifactId>\s*([^<]+)\s*</artifactId>', block)
        version_match = re.search(r'<version>\s*([^<]+)\s*</version>', block)
        scope_match = re.search(r'<scope>\s*([^<]+)\s*</scope>', block)
        if not artifact_match:
            continue
        name = artifact_match.group(1).strip()
        version = version_match.group(1).strip() if version_match else None
        scope = scope_match.group(1).strip() if scope_match else "compile"
        dep_type = "dev_dependency" if scope in ("test", "provided") else "dependency"
        deps.append(Dependency(
            name=name,
            version=version,
            dep_type=dep_type,
            source_file=source_file,
        ))
    return deps


def _parse_composer_json(content: str, source_file: str) -> List[Dependency]:
    """Parse PHP composer.json."""
    deps: List[Dependency] = []
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return deps
    for name, version in data.get("require", {}).items():
        if name == "php":
            continue
        deps.append(Dependency(
            name=name,
            version=str(version),
            dep_type="dependency",
            source_file=source_file,
        ))
    for name, version in data.get("require-dev", {}).items():
        deps.append(Dependency(
            name=name,
            version=str(version),
            dep_type="dev_dependency",
            source_file=source_file,
        ))
    return deps


def _parse_gemfile(content: str, source_file: str) -> List[Dependency]:
    """Parse Ruby Gemfile."""
    deps: List[Dependency] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped.startswith("gem "):
            continue
        match = re.match(r"gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", stripped)
        if match:
            deps.append(Dependency(
                name=match.group(1),
                version=match.group(2),
                dep_type="dependency",
                source_file=source_file,
            ))
    return deps


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_PARSERS = {
    "package.json": _parse_package_json,
    "requirements.txt": _parse_requirements_txt,
    "requirements-dev.txt": _parse_requirements_txt,
    "requirements-test.txt": _parse_requirements_txt,
    "pyproject.toml": _parse_pyproject_toml,
    "go.mod": _parse_go_mod,
    "Cargo.toml": _parse_cargo_toml,
    "pom.xml": _parse_pom_xml,
    "composer.json": _parse_composer_json,
    "Gemfile": _parse_gemfile,
}


def analyze_dependencies(files: Dict[str, str]) -> List[Dependency]:
    """
    Detect and parse dependencies from a mapping of path → content.

    Parameters
    ----------
    files:
        Dict mapping file path (relative to repo root) → file text content.

    Returns
    -------
    Flat list of Dependency objects from all recognized manifest files.
    """
    all_deps: List[Dependency] = []
    for path, content in files.items():
        import os as _os
        basename = _os.path.basename(path)
        parser = _PARSERS.get(basename)
        if parser and content:
            try:
                all_deps.extend(parser(content, path))
            except Exception:
                # Silently skip malformed manifests
                pass
    return all_deps
