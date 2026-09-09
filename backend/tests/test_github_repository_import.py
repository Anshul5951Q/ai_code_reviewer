"""Tests for GitHub repository listing, pagination headers, and importing into the local database."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.main import app
from app.schemas.github import GitHubRepoItem, GitHubStatusResponse
from app.services.github import BaseGitHubService, get_github_service


class MockRepoService(BaseGitHubService):
    """Mock service returning custom repository lists for import testing."""

    async def verify_connection(self) -> GitHubStatusResponse:
        return GitHubStatusResponse(connected=True, github_login="dev-user")

    async def list_repositories(self, limit: int = 30, **kwargs) -> list[GitHubRepoItem]:
        all_repos = [
            GitHubRepoItem(
                id=1,
                name="repo-alpha",
                full_name="org/repo-alpha",
                owner="org",
                html_url="https://github.com/org/repo-alpha",
                default_branch="main",
                visibility="public",
                language="TypeScript",
            ),
            GitHubRepoItem(
                id=2,
                name="repo-beta",
                full_name="org/repo-beta",
                owner="org",
                html_url="https://github.com/org/repo-beta",
                default_branch="main",
                visibility="private",
                language="Python",
            ),
        ]
        search = kwargs.get("search")
        if search:
            return [r for r in all_repos if search.lower() in r.name.lower()]
        return all_repos[:limit]

    async def get_repository(self, owner: str, repo: str) -> GitHubRepoItem:
        return GitHubRepoItem(
            id=1,
            name=repo,
            full_name=f"{owner}/{repo}",
            owner=owner,
            html_url=f"https://github.com/{owner}/{repo}",
            default_branch="main",
            visibility="public",
        )

    async def list_branches(self, owner: str, repo: str):
        return []

    async def list_commits(self, owner: str, repo: str, branch=None, limit=30):
        return []

    async def get_file_tree(self, owner: str, repo: str, tree_sha="HEAD", recursive=True):
        return []

    async def get_file_content(self, owner: str, repo: str, path: str, ref=None):
        return None  # type: ignore


@pytest.fixture(autouse=True)
def override_repo_service():
    mock = MockRepoService()
    app.dependency_overrides[get_github_service] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_github_service, None)


@pytest.mark.anyio
async def test_list_github_repositories_pagination_headers(client: AsyncClient):
    """GET /api/github/repositories sets pagination metadata in HTTP headers."""
    res = await client.get("/api/github/repositories?limit=10&page=1")
    assert res.status_code == 200
    assert res.headers.get("X-Page") == "1"
    assert res.headers.get("X-Per-Page") == "10"
    data = res.json()
    assert len(data) == 2


@pytest.mark.anyio
async def test_import_repository_flow(client: AsyncClient):
    """Test importing a GitHub repository into the local database."""
    payload = {
        "name": "repo-alpha",
        "full_name": "org/repo-alpha",
        "owner": "org",
        "default_branch": "main",
        "visibility": "public",
        "language": "TypeScript",
        "github_id": 1,
    }

    # 1. Import repository
    import_res = await client.post("/api/repositories", json=payload)
    assert import_res.status_code == 201
    repo = import_res.json()
    assert repo["full_name"] == "org/repo-alpha"
    assert repo["id"] is not None

    # 2. Idempotent check: importing again returns 409 Conflict
    dup_res = await client.post("/api/repositories", json=payload)
    assert dup_res.status_code == 409
    assert "already registered" in dup_res.json()["detail"].lower()


@pytest.mark.anyio
async def test_batch_import_repositories(client: AsyncClient):
    """Test importing multiple repositories sequentially."""
    repos = [
        {"name": "batch-one", "full_name": "org/batch-one", "owner": "org", "github_id": 101},
        {"name": "batch-two", "full_name": "org/batch-two", "owner": "org", "github_id": 102},
    ]

    for r in repos:
        res = await client.post("/api/repositories", json=r)
        assert res.status_code == 201

    # Verify both are returned by GET /api/repositories
    list_res = await client.get("/api/repositories")
    assert list_res.status_code == 200
    names = [x["name"] for x in list_res.json()["items"]]
    assert "batch-one" in names
    assert "batch-two" in names
