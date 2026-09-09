"""Tests for GitHub API routes and repository proxy endpoints."""
from __future__ import annotations

from typing import List, Optional
import pytest
from httpx import AsyncClient

from app.main import app
from app.schemas.github import (
    GitHubBranch,
    GitHubCommit,
    GitHubFileContent,
    GitHubRepoItem,
    GitHubStatusResponse,
    GitHubTreeItem,
)
from app.services.github import BaseGitHubService, get_github_service


class MockGitHubService(BaseGitHubService):
    """Mock implementation of BaseGitHubService for API testing."""

    async def verify_connection(self) -> GitHubStatusResponse:
        return GitHubStatusResponse(
            connected=True,
            authenticated_user="test-user",
            user_name="Test Developer",
            rate_limit_limit=5000,
            rate_limit_remaining=4950,
        )

    async def list_repositories(self, limit: int = 30) -> List[GitHubRepoItem]:
        return [
            GitHubRepoItem(
                id=101,
                name="sample-project",
                full_name="test-user/sample-project",
                owner="test-user",
                html_url="https://github.com/test-user/sample-project",
                default_branch="main",
                visibility="public",
                language="Python",
            )
        ]

    async def get_repository(self, owner: str, repo: str) -> GitHubRepoItem:
        return GitHubRepoItem(
            id=101,
            name=repo,
            full_name=f"{owner}/{repo}",
            owner=owner,
            html_url=f"https://github.com/{owner}/{repo}",
            default_branch="main",
            visibility="public",
            language="Python",
        )

    async def list_branches(self, owner: str, repo: str) -> List[GitHubBranch]:
        return [
            GitHubBranch(name="main", commit_sha="abcdef1234567890"),
            GitHubBranch(name="dev", commit_sha="123456abcdef7890"),
        ]

    async def list_commits(
        self, owner: str, repo: str, branch: Optional[str] = None, limit: int = 30
    ) -> List[GitHubCommit]:
        return [
            GitHubCommit(
                sha="abcdef1234567890",
                short_sha="abcdef1",
                message="Initial commit",
                author_name="Test Developer",
                date="2026-09-01T12:00:00Z",
            )
        ]

    async def get_file_tree(
        self, owner: str, repo: str, tree_sha: str = "HEAD", recursive: bool = True
    ) -> List[GitHubTreeItem]:
        return [
            GitHubTreeItem(path="main.py", mode="100644", type="blob", sha="sha1", size=100)
        ]

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: Optional[str] = None
    ) -> GitHubFileContent:
        return GitHubFileContent(
            path=path,
            sha="sha1",
            size=100,
            encoding="utf-8",
            content="print('hello')",
        )


@pytest.fixture(autouse=True)
def override_github_service():
    mock = MockGitHubService()
    app.dependency_overrides[get_github_service] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_github_service, None)


@pytest.mark.anyio
async def test_api_github_status(client: AsyncClient) -> None:
    res = await client.get("/api/github/status")
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is True
    assert data["authenticated_user"] == "test-user"


@pytest.mark.anyio
async def test_api_github_repositories(client: AsyncClient) -> None:
    res = await client.get("/api/github/repositories")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["full_name"] == "test-user/sample-project"


@pytest.mark.anyio
async def test_api_github_branches_and_commits(client: AsyncClient) -> None:
    branches_res = await client.get("/api/github/branches?owner=test-user&repo=sample-project")
    assert branches_res.status_code == 200
    assert len(branches_res.json()) == 2

    commits_res = await client.get("/api/github/commits?owner=test-user&repo=sample-project&branch=main")
    assert commits_res.status_code == 200
    assert len(commits_res.json()) == 1
    assert commits_res.json()[0]["short_sha"] == "abcdef1"


@pytest.mark.anyio
async def test_api_repository_github_proxy_routes(client: AsyncClient) -> None:
    # 1. Create a repository in DB
    create_res = await client.post(
        "/api/repositories",
        json={
            "name": "sample-project",
            "full_name": "test-user/sample-project",
            "owner": "test-user",
            "default_branch": "main",
            "visibility": "public",
        },
    )
    repo_id = create_res.json()["id"]

    # 2. Test branches proxy
    b_res = await client.get(f"/api/repositories/{repo_id}/branches")
    assert b_res.status_code == 200
    assert len(b_res.json()) == 2

    # 3. Test commits proxy
    c_res = await client.get(f"/api/repositories/{repo_id}/commits?branch=main")
    assert c_res.status_code == 200
    assert len(c_res.json()) == 1

    # 4. Test tree proxy
    t_res = await client.get(f"/api/repositories/{repo_id}/tree")
    assert t_res.status_code == 200
    assert len(t_res.json()) == 1

    # 5. Test content proxy
    cnt_res = await client.get(f"/api/repositories/{repo_id}/content?path=main.py")
    assert cnt_res.status_code == 200
    assert cnt_res.json()["content"] == "print('hello')"
