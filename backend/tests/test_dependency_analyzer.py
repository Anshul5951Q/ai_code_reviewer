"""Tests for dependency_analyzer."""
from __future__ import annotations

import pytest
from app.analysis.dependency_analyzer import analyze_dependencies, Dependency


PACKAGE_JSON = """{
  "name": "my-app",
  "dependencies": {
    "react": "^18.0.0",
    "next": "13.4.0",
    "axios": "^1.5.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "jest": "^29.0.0"
  },
  "peerDependencies": {
    "react-dom": ">=18"
  }
}"""

REQUIREMENTS_TXT = """\
# Main deps
fastapi==0.115.0
uvicorn[standard]>=0.30.0
httpx
sqlalchemy>=2.0; python_version>="3.8"
# Dev deps
pytest
"""

PYPROJECT_TOML = """\
[tool.poetry]
name = "my-project"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.115.0"
sqlalchemy = "^2.0"

[tool.poetry.dev-dependencies]
pytest = "^8.0"
black = "*"
"""

GO_MOD = """\
module github.com/user/myapp

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/labstack/echo v4.11.0
    golang.org/x/crypto v0.14.0 // indirect
)

require github.com/some/direct v1.0.0
"""

CARGO_TOML = """\
[package]
name = "my-app"
version = "0.1.0"

[dependencies]
tokio = { version = "1.0", features = ["full"] }
serde = "1.0"

[dev-dependencies]
tempfile = "3.0"
"""

POM_XML = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
      <version>3.1.0</version>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <version>3.1.0</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
"""

COMPOSER_JSON = """\
{
  "require": {
    "php": ">=8.1",
    "laravel/framework": "^10.0",
    "guzzlehttp/guzzle": "^7.5"
  },
  "require-dev": {
    "phpunit/phpunit": "^10.0"
  }
}
"""

GEMFILE = """\
source 'https://rubygems.org'

gem 'rails', '~> 7.0'
gem 'pg', '~> 1.5'
gem 'devise'
"""


class TestPackageJson:
    def test_parses_dependencies(self):
        files = {"package.json": PACKAGE_JSON}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "react" in names
        assert "next" in names
        assert "axios" in names

    def test_parses_dev_dependencies(self):
        files = {"package.json": PACKAGE_JSON}
        deps = analyze_dependencies(files)
        dev = [d for d in deps if d.dep_type == "dev_dependency"]
        names = {d.name for d in dev}
        assert "typescript" in names
        assert "jest" in names

    def test_parses_peer_dependencies(self):
        files = {"package.json": PACKAGE_JSON}
        deps = analyze_dependencies(files)
        peer = [d for d in deps if d.dep_type == "peer_dependency"]
        assert any(d.name == "react-dom" for d in peer)

    def test_invalid_json_returns_empty(self):
        files = {"package.json": "not json {{{"}
        deps = analyze_dependencies(files)
        assert deps == []


class TestRequirementsTxt:
    def test_parses_pinned_version(self):
        files = {"requirements.txt": REQUIREMENTS_TXT}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "fastapi" in names

    def test_skips_comments(self):
        files = {"requirements.txt": REQUIREMENTS_TXT}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "Main deps" not in names

    def test_parses_no_version(self):
        files = {"requirements.txt": REQUIREMENTS_TXT}
        deps = analyze_dependencies(files)
        httpx = next((d for d in deps if d.name == "httpx"), None)
        assert httpx is not None
        assert httpx.version is None


class TestPyprojectToml:
    def test_parses_poetry_deps(self):
        files = {"pyproject.toml": PYPROJECT_TOML}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "fastapi" in names
        assert "sqlalchemy" in names

    def test_skips_python_dep(self):
        files = {"pyproject.toml": PYPROJECT_TOML}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "python" not in names


class TestGoMod:
    def test_parses_require_block(self):
        files = {"go.mod": GO_MOD}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "github.com/gin-gonic/gin" in names
        assert "github.com/labstack/echo" in names

    def test_indirect_is_dev(self):
        files = {"go.mod": GO_MOD}
        deps = analyze_dependencies(files)
        indirect = [d for d in deps if "crypto" in d.name]
        assert indirect
        assert indirect[0].dep_type == "dev_dependency"

    def test_parses_single_line_require(self):
        files = {"go.mod": GO_MOD}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "github.com/some/direct" in names


class TestCargoToml:
    def test_parses_dependencies(self):
        files = {"Cargo.toml": CARGO_TOML}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "tokio" in names
        assert "serde" in names

    def test_dev_deps_classified_correctly(self):
        files = {"Cargo.toml": CARGO_TOML}
        deps = analyze_dependencies(files)
        dev = [d for d in deps if d.dep_type == "dev_dependency"]
        assert any(d.name == "tempfile" for d in dev)


class TestPomXml:
    def test_parses_dependencies(self):
        files = {"pom.xml": POM_XML}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "spring-boot-starter-web" in names

    def test_test_scope_is_dev(self):
        files = {"pom.xml": POM_XML}
        deps = analyze_dependencies(files)
        test_dep = next(d for d in deps if d.name == "spring-boot-starter-test")
        assert test_dep.dep_type == "dev_dependency"


class TestComposerJson:
    def test_parses_require(self):
        files = {"composer.json": COMPOSER_JSON}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "laravel/framework" in names
        assert "guzzlehttp/guzzle" in names

    def test_skips_php_itself(self):
        files = {"composer.json": COMPOSER_JSON}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "php" not in names


class TestGemfile:
    def test_parses_gems(self):
        files = {"Gemfile": GEMFILE}
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "rails" in names
        assert "pg" in names
        assert "devise" in names


class TestEdgeCases:
    def test_empty_files_dict_returns_empty(self):
        assert analyze_dependencies({}) == []

    def test_empty_content_skipped(self):
        files = {"requirements.txt": ""}
        deps = analyze_dependencies(files)
        assert deps == []

    def test_unknown_filename_ignored(self):
        files = {"random_file.txt": "some random content\nnot deps"}
        deps = analyze_dependencies(files)
        assert deps == []

    def test_multiple_manifests_combined(self):
        files = {
            "package.json": PACKAGE_JSON,
            "requirements.txt": REQUIREMENTS_TXT,
        }
        deps = analyze_dependencies(files)
        names = {d.name for d in deps}
        assert "react" in names
        assert "fastapi" in names

    def test_source_file_recorded(self):
        files = {"requirements.txt": REQUIREMENTS_TXT}
        deps = analyze_dependencies(files)
        sources = {d.source_file for d in deps}
        assert "requirements.txt" in sources

    def test_dependency_to_dict(self):
        dep = Dependency(name="react", version="^18.0", dep_type="dependency", source_file="package.json")
        d = dep.to_dict()
        assert d["name"] == "react"
        assert d["type"] == "dependency"
        assert d["source_file"] == "package.json"
