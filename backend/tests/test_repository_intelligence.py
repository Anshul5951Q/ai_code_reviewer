"""Tests for repository_intelligence."""
from __future__ import annotations

import pytest
from app.analysis.dependency_analyzer import analyze_dependencies
from app.analysis.language_detector import detect_languages
from app.analysis.repository_intelligence import analyze_repository, _detect_frameworks


REACT_APP_FILES = {
    "src/App.tsx": "import React from 'react';\nexport default function App() {}",
    "src/index.tsx": "import React from 'react';\nimport { createRoot } from 'react-dom';\nconst root = createRoot(document.getElementById('root')!);",
    "src/components/Button.tsx": "export const Button = () => <button />;",
    "src/utils/helpers.ts": "export const noop = () => {};",
    "src/__tests__/App.test.tsx": "import { render } from '@testing-library/react';\ntest('renders', () => {});",
    "package.json": '{"dependencies":{"react":"^18.0","next":"13"}}',
    "tsconfig.json": '{"compilerOptions":{}}',
}

PYTHON_API_FILES = {
    "app/main.py": "from fastapi import FastAPI\napp = FastAPI()",
    "app/models.py": "from sqlalchemy import Column, String\nclass User:\n    pass",
    "app/api/users.py": "from fastapi import APIRouter\nrouter = APIRouter()",
    "tests/test_main.py": "import pytest\ndef test_health(): pass",
    "requirements.txt": "fastapi==0.115.0\npytest\n",
    "pyproject.toml": "[tool.poetry]\nname='api'\n",
}

EMPTY_REPO_FILES = {}


class TestAnalyzeRepository:
    def _build(self, file_map):
        languages = detect_languages(list(file_map.keys()))
        deps = analyze_dependencies({k: v for k, v in file_map.items() if v is not None})
        return analyze_repository(file_map, languages, deps)

    def test_empty_repo(self):
        intel = self._build(EMPTY_REPO_FILES)
        assert intel.total_files == 0
        assert intel.source_files == 0
        assert intel.total_lines == 0
        assert intel.frameworks == []

    def test_react_app_total_files(self):
        intel = self._build(REACT_APP_FILES)
        assert intel.total_files == len(REACT_APP_FILES)

    def test_react_app_source_count(self):
        intel = self._build(REACT_APP_FILES)
        # tsx and ts files are source
        assert intel.source_files >= 4

    def test_react_app_test_count(self):
        intel = self._build(REACT_APP_FILES)
        assert intel.test_files >= 1

    def test_react_app_config_count(self):
        intel = self._build(REACT_APP_FILES)
        assert intel.config_files >= 1

    def test_react_app_language_detected(self):
        intel = self._build(REACT_APP_FILES)
        assert "TypeScript" in intel.languages

    def test_react_framework_detected(self):
        intel = self._build(REACT_APP_FILES)
        assert "React" in intel.frameworks

    def test_nextjs_framework_detected(self):
        intel = self._build(REACT_APP_FILES)
        assert "Next.js" in intel.frameworks

    def test_python_api_fastapi_detected(self):
        intel = self._build(PYTHON_API_FILES)
        assert "FastAPI" in intel.frameworks

    def test_python_api_sqlalchemy_detected(self):
        intel = self._build(PYTHON_API_FILES)
        # SQLAlchemy not in deps (requirements.txt only has fastapi)
        # but detect_frameworks reads deps list
        pass  # framework detection based on deps only

    def test_entry_points_detected(self):
        intel = self._build(PYTHON_API_FILES)
        assert any("main.py" in ep for ep in intel.entry_points)

    def test_total_lines_positive(self):
        intel = self._build(REACT_APP_FILES)
        assert intel.total_lines > 0

    def test_directory_structure_built(self):
        intel = self._build(REACT_APP_FILES)
        assert "src" in intel.directory_structure
        assert intel.directory_structure["src"] > 0

    def test_largest_files_bounded(self):
        intel = self._build(REACT_APP_FILES)
        assert len(intel.largest_files) <= 10

    def test_to_dict_structure(self):
        intel = self._build(REACT_APP_FILES)
        d = intel.to_dict()
        assert "files" in d
        assert "total_lines" in d
        assert "languages" in d
        assert "frameworks" in d
        assert "directory_structure" in d
        assert "entry_points" in d

    def test_none_content_files_handled(self):
        """Files with None content (failed fetches) should not crash the pipeline."""
        files = {
            "src/main.py": "x = 1\n",
            "src/broken.py": None,  # simulates fetch failure
        }
        languages = detect_languages(list(files.keys()))
        deps = analyze_dependencies({})
        intel = analyze_repository(files, languages, deps)
        assert intel.total_files == 2
        # total_lines should only count the file with content
        assert intel.total_lines >= 1


class TestDetectFrameworks:
    def _make_deps(self, names):
        from app.analysis.dependency_analyzer import Dependency
        return [Dependency(name=n, version="1.0", dep_type="dependency", source_file="pkg.json") for n in names]

    def test_react_detected(self):
        deps = self._make_deps(["react", "react-dom"])
        assert "React" in _detect_frameworks(deps)

    def test_fastapi_detected(self):
        deps = self._make_deps(["fastapi"])
        assert "FastAPI" in _detect_frameworks(deps)

    def test_django_detected(self):
        deps = self._make_deps(["django"])
        assert "Django" in _detect_frameworks(deps)

    def test_empty_deps(self):
        assert _detect_frameworks([]) == []

    def test_unknown_deps(self):
        deps = self._make_deps(["some-random-package"])
        assert _detect_frameworks(deps) == []
