"""Unit tests for GitHubService with 100% mocked HTTP transport."""
from __future__ import annotations

import base64
import json
import pytest
import httpx

from app.services.github import (
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
    GitHubService,
)


@pytest.mark.anyio
async def test_github_service_verify_connection_unauthenticated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rate_limit":
            return httpx.Response(
                200,
                json={"resources": {"core": {"limit": 60, "remaining": 55, "reset": 1700000000}}},
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = GitHubService(token=None, client=client)
    status = await service.verify_connection()
    assert status.connected is False
    assert status.rate_limit_limit == 60
    assert status.rate_limit_remaining == 55
    assert "No GITHUB_TOKEN" in (status.error or "")


@pytest.mark.anyio
async def test_github_service_verify_connection_authenticated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "octocat", "name": "The Octocat"})
        if request.url.path == "/rate_limit":
            return httpx.Response(
                200,
                json={"resources": {"core": {"limit": 5000, "remaining": 4990, "reset": 1700000000}}},
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = GitHubService(token="ghp_mocktoken123", client=client)
    status = await service.verify_connection()
    assert status.connected is True
    assert status.authenticated_user == "octocat"
    assert status.user_name == "The Octocat"
    assert status.rate_limit_limit == 5000


@pytest.mark.anyio
async def test_github_service_list_repositories() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" in request.headers
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1296269,
                    "name": "Hello-World",
                    "full_name": "octocat/Hello-World",
                    "owner": {"login": "octocat"},
                    "html_url": "https://github.com/octocat/Hello-World",
                    "default_branch": "master",
                    "private": False,
                    "language": "Ruby",
                    "description": "My first repository",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ],
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = GitHubService(token="mock", client=client)
    repos = await service.list_repositories()
    assert len(repos) == 1
    assert repos[0].full_name == "octocat/Hello-World"
    assert repos[0].owner == "octocat"
    assert repos[0].language == "Ruby"


@pytest.mark.anyio
async def test_github_service_list_branches_and_commits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/octocat/Hello-World/branches":
            return httpx.Response(
                200,
                json=[
                    {"name": "master", "commit": {"sha": "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"}},
                    {"name": "test-branch", "commit": {"sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e"}},
                ],
            )
        if request.url.path == "/repos/octocat/Hello-World/commits":
            return httpx.Response(
                200,
                json=[
                    {
                        "sha": "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",
                        "commit": {
                            "message": "Update README.md",
                            "author": {"name": "The Octocat", "email": "octocat@github.com", "date": "2026-01-02T15:00:00Z"},
                        },
                        "html_url": "https://github.com/octocat/Hello-World/commit/7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",
                    }
                ],
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = GitHubService(token="mock", client=client)

    branches = await service.list_branches("octocat", "Hello-World")
    assert len(branches) == 2
    assert branches[0].name == "master"
    assert branches[0].commit_sha == "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"

    commits = await service.list_commits("octocat", "Hello-World", branch="master")
    assert len(commits) == 1
    assert commits[0].short_sha == "7fd1a60"
    assert commits[0].message == "Update README.md"
    assert commits[0].author_name == "The Octocat"


@pytest.mark.anyio
async def test_github_service_file_tree_and_content() -> None:
    test_content = "def hello():\n    print('Hello World')\n"
    b64_content = base64.b64encode(test_content.encode("utf-8")).decode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/git/trees/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "sha": "tree123",
                    "tree": [
                        {"path": "src/main.py", "mode": "100644", "type": "blob", "sha": "blob123", "size": 42},
                        {"path": "README.md", "mode": "100644", "type": "blob", "sha": "blob456", "size": 128},
                    ],
                },
            )
        if "/contents/src/main.py" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "path": "src/main.py",
                    "sha": "blob123",
                    "size": 42,
                    "encoding": "base64",
                    "content": b64_content,
                },
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = GitHubService(token="mock", client=client)

    tree = await service.get_file_tree("octocat", "Hello-World")
    assert len(tree) == 2
    assert tree[0].path == "src/main.py"

    file_obj = await service.get_file_content("octocat", "Hello-World", "src/main.py")
    assert file_obj.path == "src/main.py"
    assert file_obj.content == test_content


@pytest.mark.anyio
async def test_github_service_error_handling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(401, json={"message": "Bad credentials"})
        if request.url.path == "/repos/org/secret":
            return httpx.Response(404, json={"message": "Not Found"})
        if request.url.path == "/rate_exceeded":
            return httpx.Response(403, json={"message": "API rate limit exceeded for user"})
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = GitHubService(token="bad-token", client=client)

    with pytest.raises(GitHubAuthError):
        await service._request("GET", "/user")

    with pytest.raises(GitHubResourceNotFoundError):
        await service._request("GET", "/repos/org/secret")

    with pytest.raises(GitHubRateLimitError):
        await service._request("GET", "/rate_exceeded")
