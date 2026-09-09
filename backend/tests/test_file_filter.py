"""Tests for FileFilter."""
from __future__ import annotations

import pytest
from app.analysis.file_filter import FileFilter, DEFAULT_MAX_FILE_SIZE_BYTES


@pytest.fixture
def ff() -> FileFilter:
    return FileFilter()


class TestSourceInclusion:
    def test_typescript_included(self, ff):
        assert ff.should_include("src/components/Button.tsx") is True

    def test_python_included(self, ff):
        assert ff.should_include("backend/app/main.py") is True

    def test_go_included(self, ff):
        assert ff.should_include("cmd/server/main.go") is True

    def test_rust_included(self, ff):
        assert ff.should_include("src/lib.rs") is True

    def test_java_included(self, ff):
        assert ff.should_include("src/Main.java") is True

    def test_cpp_included(self, ff):
        assert ff.should_include("src/engine.cpp") is True

    def test_csharp_included(self, ff):
        assert ff.should_include("src/Program.cs") is True

    def test_ruby_included(self, ff):
        assert ff.should_include("app/models/user.rb") is True

    def test_vue_included(self, ff):
        assert ff.should_include("components/Header.vue") is True

    def test_svelte_included(self, ff):
        assert ff.should_include("src/App.svelte") is True


class TestConfigInclusion:
    def test_package_json_included(self, ff):
        assert ff.should_include("package.json") is True

    def test_requirements_txt_included(self, ff):
        assert ff.should_include("requirements.txt") is True

    def test_pyproject_toml_included(self, ff):
        assert ff.should_include("pyproject.toml") is True

    def test_go_mod_included(self, ff):
        assert ff.should_include("go.mod") is True

    def test_cargo_toml_included(self, ff):
        assert ff.should_include("Cargo.toml") is True

    def test_dockerfile_included(self, ff):
        assert ff.should_include("Dockerfile") is True

    def test_tsconfig_included(self, ff):
        assert ff.should_include("tsconfig.json") is True

    def test_yaml_ci_included(self, ff):
        assert ff.should_include(".github/workflows/ci.yml") is True

    def test_markdown_readme_included(self, ff):
        assert ff.should_include("README.md") is True


class TestExclusion:
    def test_node_modules_excluded(self, ff):
        assert ff.should_include("node_modules/react/index.js") is False

    def test_venv_excluded(self, ff):
        assert ff.should_include("venv/lib/python3.11/site-packages/flask/__init__.py") is False

    def test_pycache_excluded(self, ff):
        assert ff.should_include("app/__pycache__/main.cpython-311.pyc") is False

    def test_dist_excluded(self, ff):
        assert ff.should_include("dist/bundle.js") is False

    def test_next_excluded(self, ff):
        assert ff.should_include(".next/static/chunks/main.js") is False

    def test_png_excluded(self, ff):
        assert ff.should_include("public/logo.png") is False

    def test_jpg_excluded(self, ff):
        assert ff.should_include("assets/hero.jpg") is False

    def test_pyc_excluded(self, ff):
        assert ff.should_include("app/models.pyc") is False

    def test_zip_excluded(self, ff):
        assert ff.should_include("archive.zip") is False

    def test_exe_excluded(self, ff):
        assert ff.should_include("build/app.exe") is False

    def test_ds_store_excluded(self, ff):
        assert ff.should_include(".DS_Store") is False

    def test_gitignore_excluded(self, ff):
        assert ff.should_include(".gitignore") is False

    def test_coverage_dir_excluded(self, ff):
        assert ff.should_include("coverage/lcov.info") is False

    def test_target_dir_excluded(self, ff):
        assert ff.should_include("target/debug/main") is False


class TestSizeFilter:
    def test_oversized_file_excluded(self, ff):
        assert ff.should_include("src/huge.ts", size=DEFAULT_MAX_FILE_SIZE_BYTES + 1) is False

    def test_max_size_included(self, ff):
        assert ff.should_include("src/ok.ts", size=DEFAULT_MAX_FILE_SIZE_BYTES) is True

    def test_no_size_included(self, ff):
        assert ff.should_include("src/no_size.py") is True

    def test_custom_max_size(self):
        ff = FileFilter(max_file_size_bytes=100)
        assert ff.should_include("src/big.py", size=101) is False
        assert ff.should_include("src/small.py", size=50) is True


class TestClassification:
    def test_classify_source(self, ff):
        assert ff.classify_file("src/main.py") == "source"

    def test_classify_test(self, ff):
        assert ff.classify_file("tests/test_main.py") == "test"

    def test_classify_test_by_name(self, ff):
        assert ff.classify_file("src/button.test.tsx") == "test"

    def test_classify_config(self, ff):
        assert ff.classify_file("package.json") == "config"
