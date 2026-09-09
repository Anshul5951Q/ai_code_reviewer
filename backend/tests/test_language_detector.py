"""Tests for language_detector."""
from __future__ import annotations

import pytest
from app.analysis.language_detector import detect_languages, LanguageStat


class TestDetectLanguages:
    def test_empty_list_returns_empty(self):
        result = detect_languages([])
        assert result == {}

    def test_single_language(self):
        paths = ["src/main.py", "src/utils.py", "src/models.py"]
        result = detect_languages(paths)
        assert "Python" in result
        assert result["Python"].files == 3
        assert result["Python"].percentage == 100.0

    def test_mixed_languages(self):
        paths = [
            "frontend/index.tsx",
            "frontend/app.tsx",
            "backend/main.py",
            "backend/utils.py",
            "backend/models.py",
        ]
        result = detect_languages(paths)
        assert "TypeScript" in result
        assert "Python" in result
        ts = result["TypeScript"]
        py = result["Python"]
        assert ts.files == 2
        assert py.files == 3
        # Percentages sum to 100
        total_pct = sum(s.percentage for s in result.values())
        assert abs(total_pct - 100.0) < 0.5

    def test_unknown_extensions_skipped(self):
        paths = ["README.xyz", "data.abc", "main.py"]
        result = detect_languages(paths)
        # Only main.py has known extension
        assert "Python" in result
        assert len(result) == 1

    def test_sorted_by_file_count(self):
        paths = ["a.py", "b.py", "c.py", "x.ts"]
        result = detect_languages(paths)
        keys = list(result.keys())
        assert keys[0] == "Python"
        assert keys[1] == "TypeScript"

    def test_javascript_detected(self):
        paths = ["src/index.js", "src/app.jsx", "src/utils.mjs"]
        result = detect_languages(paths)
        assert "JavaScript" in result
        assert result["JavaScript"].files == 3

    def test_go_detected(self):
        paths = ["main.go", "server.go"]
        result = detect_languages(paths)
        assert "Go" in result
        assert result["Go"].files == 2

    def test_case_insensitive_extension(self):
        # Extensions should be lowercased before lookup
        paths = ["README.MD"]
        result = detect_languages(paths)
        # .MD is not in our map (only .md), but we lower-case before lookup
        # so it should match .md → Markdown
        assert "Markdown" in result

    def test_percentages_correct(self):
        paths = ["a.ts"] * 3 + ["b.py"] * 1
        result = detect_languages(paths)
        ts_pct = result["TypeScript"].percentage
        py_pct = result["Python"].percentage
        assert abs(ts_pct - 75.0) < 0.1
        assert abs(py_pct - 25.0) < 0.1

    def test_language_stat_to_dict(self):
        stat = LanguageStat(language="Python", files=10, percentage=80.0)
        d = stat.to_dict()
        assert d == {"files": 10, "percentage": 80.0}
