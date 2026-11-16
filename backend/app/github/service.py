from __future__ import annotations

import base64
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import TokenDecryptionError, decrypt_token
from app.db.session import get_db
from app.github.exceptions import (
    GitHubAuthError,
    GitHubError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
)
from app.models.github_connection import GitHubConnection
from app.schemas.github import (
    GitHubBranch,
    GitHubCommit,
    GitHubFileContent,
    GitHubRepoItem,
    GitHubStatusResponse,
    GitHubTreeItem,
)

logger = logging.getLogger("ai_code_reviewer.github.service")


class BaseGitHubService(ABC):
    """Abstract interface for GitHub operations."""

    @abstractmethod
    async def verify_connection(self) -> GitHubStatusResponse:
        pass

    @abstractmethod
    async def list_repositories(self, limit: int = 30, **kwargs: Any) -> List[GitHubRepoItem]:
        pass

    @abstractmethod
    async def get_repository(self, owner: str, repo: str) -> GitHubRepoItem:
        pass

    @abstractmethod
    async def list_branches(self, owner: str, repo: str) -> List[GitHubBranch]:
        pass

    @abstractmethod
    async def list_commits(
        self, owner: str, repo: str, branch: Optional[str] = None, limit: int = 30
    ) -> List[GitHubCommit]:
        pass

    @abstractmethod
    async def get_file_tree(
        self, owner: str, repo: str, tree_sha: str = "HEAD", recursive: bool = True
    ) -> List[GitHubTreeItem]:
        pass

    @abstractmethod
    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: Optional[str] = None
    ) -> GitHubFileContent:
        pass


_GITHUB_CACHE: Dict[str, Tuple[float, Any]] = {}
_GITHUB_CACHE_TTL_SECONDS: float = 60.0


def clear_github_cache() -> None:
    """Clear in-memory GitHub cache (for testing or manual cache busting)."""
    _GITHUB_CACHE.clear()


class GitHubService(BaseGitHubService):
    """Production GitHub client using httpx with clean error handling and session-aware decrypted tokens."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.token = token
        self.base_url = (base_url or settings.github_api_base_url).rstrip("/")
        self._external_client = client

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AICodeReviewer/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _extract_rate_limits(self, response: httpx.Response) -> tuple[Optional[int], Optional[int], Optional[int]]:
        limit = None
        remaining = None
        reset_ts = None
        try:
            if "X-RateLimit-Limit" in response.headers:
                limit = int(response.headers["X-RateLimit-Limit"])
            if "X-RateLimit-Remaining" in response.headers:
                remaining = int(response.headers["X-RateLimit-Remaining"])
            if "X-RateLimit-Reset" in response.headers:
                reset_ts = int(response.headers["X-RateLimit-Reset"])
        except (ValueError, TypeError):
            pass
        return limit, remaining, reset_ts

    def _handle_error_response(self, response: httpx.Response) -> None:
        body_msg = ""
        try:
            body = response.json()
            if isinstance(body, dict) and "message" in body:
                body_msg = body["message"]
        except Exception:
            pass

        limit, remaining, _ = self._extract_rate_limits(response)

        if response.status_code == 429 or (
            response.status_code == 403 and ("rate limit" in body_msg.lower() or remaining == 0)
        ):
            raise GitHubRateLimitError("GitHub API rate limit exceeded")

        if response.status_code in (401, 403):
            raise GitHubAuthError(f"GitHub authentication failed: {body_msg}" if body_msg else "GitHub authentication failed")

        if response.status_code == 404:
            raise GitHubResourceNotFoundError("Requested GitHub resource not found")

        error_msg = f"GitHub API error ({response.status_code})"
        if body_msg:
            error_msg = f"GitHub API error: {body_msg}"
        raise GitHubError(error_msg, status_code=response.status_code)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        req_headers = self._get_headers()
        if headers:
            req_headers.update(headers)

        async def _exec(client: httpx.AsyncClient) -> httpx.Response:
            return await client.request(method, url, headers=req_headers, params=params, timeout=15.0)

        try:
            if self._external_client:
                response = await _exec(self._external_client)
            else:
                async with httpx.AsyncClient() as client:
                    response = await _exec(client)
        except (GitHubError, GitHubRateLimitError, GitHubAuthError, GitHubResourceNotFoundError):
            raise
        except Exception as exc:
            logger.error("Failed to connect to GitHub API: %s", type(exc).__name__)
            raise GitHubError(
                "Failed to connect to GitHub API. Please check your network connection.",
                status_code=502,
            ) from None

        if response.status_code >= 400:
            self._handle_error_response(response)

        return response

    async def verify_connection(self) -> GitHubStatusResponse:
        """Verify connection status, authenticated user, and rate limits with short TTL caching."""
        import hashlib

        use_cache = self._external_client is None
        token_hash = hashlib.sha256((self.token or "none").encode()).hexdigest()[:16]
        cache_key = f"verify:{token_hash}"
        now = time.monotonic()
        if use_cache and cache_key in _GITHUB_CACHE:
            cached_time, cached_res = _GITHUB_CACHE[cache_key]
            if (now - cached_time) < 30.0:
                return cached_res

        rate_limit_limit = None
        rate_limit_remaining = None
        rate_limit_reset = None
        oauth_configured = bool(settings.github_client_id and settings.github_client_secret)

        try:
            rl_resp = await self._request("GET", "/rate_limit")
            rl_data = rl_resp.json()
            core = rl_data.get("resources", {}).get("core", {})
            rate_limit_limit = core.get("limit")
            rate_limit_remaining = core.get("remaining")
            rate_limit_reset = core.get("reset")
        except Exception:
            pass

        if not self.token:
            resp = GitHubStatusResponse(
                connected=False,
                rate_limit_limit=rate_limit_limit,
                rate_limit_remaining=rate_limit_remaining,
                rate_limit_reset=rate_limit_reset,
                error="No GITHUB_TOKEN configured or connected",
                oauth_configured=oauth_configured,
            )
            if use_cache:
                _GITHUB_CACHE[cache_key] = (now, resp)
            return resp

        try:
            user_resp = await self._request("GET", "/user")
            data = user_resp.json()
            login = data.get("login")
            name = data.get("name")
            avatar_url = data.get("avatar_url")
            raw_scopes = user_resp.headers.get("X-OAuth-Scopes", "")
            scopes = [s.strip() for s in raw_scopes.split(",") if s.strip()]

            resp = GitHubStatusResponse(
                connected=True,
                github_login=login,
                avatar_url=avatar_url,
                authenticated_user=login,
                user_name=name,
                scopes=scopes,
                rate_limit_limit=rate_limit_limit,
                rate_limit_remaining=rate_limit_remaining,
                rate_limit_reset=rate_limit_reset,
                oauth_configured=oauth_configured,
            )
            if use_cache:
                _GITHUB_CACHE[cache_key] = (now, resp)
            return resp
        except GitHubAuthError:
            resp = GitHubStatusResponse(
                connected=False,
                rate_limit_limit=rate_limit_limit,
                rate_limit_remaining=rate_limit_remaining,
                rate_limit_reset=rate_limit_reset,
                error="GitHub authentication token has expired or is invalid.",
                oauth_configured=oauth_configured,
            )
            if use_cache:
                _GITHUB_CACHE[cache_key] = (now, resp)
            return resp
        except GitHubRateLimitError:
            resp = GitHubStatusResponse(
                connected=False,
                rate_limit_limit=rate_limit_limit,
                rate_limit_remaining=rate_limit_remaining,
                rate_limit_reset=rate_limit_reset,
                error="GitHub API rate limit exceeded.",
                oauth_configured=oauth_configured,
            )
            if use_cache:
                _GITHUB_CACHE[cache_key] = (now, resp)
            return resp
        except GitHubError as e:
            return GitHubStatusResponse(
                connected=False,
                rate_limit_limit=rate_limit_limit,
                rate_limit_remaining=rate_limit_remaining,
                rate_limit_reset=rate_limit_reset,
                error=e.message,
                oauth_configured=oauth_configured,
            )

    async def list_repositories(
        self,
        limit: int = 30,
        page: int = 1,
        repo_type: Optional[str] = None,
        visibility: Optional[str] = None,
        affiliation: Optional[str] = None,
        search: Optional[str] = None,
        **kwargs: Any,
    ) -> List[GitHubRepoItem]:
        """List repositories accessible to the current connection."""
        params: Dict[str, Any] = {
            "per_page": min(limit, 100),
            "page": max(page, 1),
            "sort": "updated",
            "direction": "desc",
        }
        if repo_type:
            params["type"] = repo_type
        if visibility:
            params["visibility"] = visibility
        if affiliation:
            params["affiliation"] = affiliation

        resp = await self._request("GET", "/user/repos", params=params)
        repos_data = resp.json()

        items: List[GitHubRepoItem] = []
        for r in repos_data:
            if not isinstance(r, dict):
                continue
            if search:
                query_lower = search.lower()
                name_match = query_lower in r.get("name", "").lower()
                full_name_match = query_lower in r.get("full_name", "").lower()
                if not (name_match or full_name_match):
                    continue

            owner_login = r.get("owner", {}).get("login", "") if isinstance(r.get("owner"), dict) else ""
            items.append(
                GitHubRepoItem(
                    id=r["id"],
                    name=r["name"],
                    full_name=r.get("full_name", f"{owner_login}/{r['name']}"),
                    owner=owner_login,
                    html_url=r.get("html_url", f"https://github.com/{owner_login}/{r['name']}"),
                    default_branch=r.get("default_branch", "main"),
                    visibility="private" if r.get("private") else "public",
                    language=r.get("language"),
                    description=r.get("description"),
                    updated_at=r.get("updated_at"),
                )
            )
        return items

    async def get_repository(self, owner: str, repo: str) -> GitHubRepoItem:
        """Fetch metadata for a single repository with in-memory caching."""
        use_cache = self._external_client is None
        cache_key = f"repo:{owner.lower()}/{repo.lower()}"
        now = time.monotonic()
        if use_cache and cache_key in _GITHUB_CACHE:
            cached_time, cached_item = _GITHUB_CACHE[cache_key]
            if (now - cached_time) < _GITHUB_CACHE_TTL_SECONDS:
                return cached_item

        try:
            resp = await self._request("GET", f"/repos/{owner}/{repo}")
            r = resp.json()
            owner_login = r.get("owner", {}).get("login", owner) if isinstance(r.get("owner"), dict) else owner
            item = GitHubRepoItem(
                id=r["id"],
                name=r["name"],
                full_name=r.get("full_name", f"{owner_login}/{r['name']}"),
                owner=owner_login,
                html_url=r.get("html_url", f"https://github.com/{owner_login}/{r['name']}"),
                default_branch=r.get("default_branch", "main"),
                visibility="private" if r.get("private") else "public",
                language=r.get("language"),
                description=r.get("description"),
                updated_at=r.get("updated_at"),
            )
            if use_cache:
                _GITHUB_CACHE[cache_key] = (now, item)
            return item
        except GitHubRateLimitError:
            if cache_key in _GITHUB_CACHE:
                logger.warning("GitHub rate limit hit; serving cached repo metadata for %s/%s", owner, repo)
                return _GITHUB_CACHE[cache_key][1]
            raise

    async def list_branches(self, owner: str, repo: str) -> List[GitHubBranch]:
        """List branches for a repository with in-memory caching."""
        use_cache = self._external_client is None
        cache_key = f"branches:{owner.lower()}/{repo.lower()}"
        now = time.monotonic()
        if use_cache and cache_key in _GITHUB_CACHE:
            cached_time, cached_branches = _GITHUB_CACHE[cache_key]
            if (now - cached_time) < _GITHUB_CACHE_TTL_SECONDS:
                return cached_branches

        try:
            resp = await self._request("GET", f"/repos/{owner}/{repo}/branches", params={"per_page": 100})
            branches_data = resp.json()

            branches: List[GitHubBranch] = []
            for b in branches_data:
                if isinstance(b, dict):
                    commit_sha = b.get("commit", {}).get("sha", "") if isinstance(b.get("commit"), dict) else ""
                    branches.append(
                        GitHubBranch(
                            name=b["name"],
                            commit_sha=commit_sha,
                            protected=b.get("protected", False),
                        )
                    )
            if use_cache:
                _GITHUB_CACHE[cache_key] = (now, branches)
            return branches
        except GitHubRateLimitError:
            if cache_key in _GITHUB_CACHE:
                logger.warning("GitHub rate limit hit; serving cached branches for %s/%s", owner, repo)
                return _GITHUB_CACHE[cache_key][1]
            raise

    async def list_commits(
        self, owner: str, repo: str, branch: Optional[str] = None, limit: int = 30
    ) -> List[GitHubCommit]:
        """List commits for a repository with in-memory caching."""
        use_cache = self._external_client is None
        branch_key = branch or "default"
        cache_key = f"commits:{owner.lower()}/{repo.lower()}:{branch_key}:{limit}"
        now = time.monotonic()
        if use_cache and cache_key in _GITHUB_CACHE:
            cached_time, cached_commits = _GITHUB_CACHE[cache_key]
            if (now - cached_time) < _GITHUB_CACHE_TTL_SECONDS:
                return cached_commits

        params: Dict[str, Any] = {"per_page": min(limit, 100)}
        if branch:
            params["sha"] = branch

        try:
            resp = await self._request("GET", f"/repos/{owner}/{repo}/commits", params=params)
            commits_data = resp.json()

            commits: List[GitHubCommit] = []
            for c in commits_data:
                if not isinstance(c, dict):
                    continue
                sha = c["sha"]
                commit_obj = c.get("commit", {})
                author_obj = commit_obj.get("author", {})
                commits.append(
                    GitHubCommit(
                        sha=sha,
                        short_sha=sha[:7],
                        message=commit_obj.get("message", "").splitlines()[0] if commit_obj.get("message") else "",
                        author_name=author_obj.get("name", "Unknown"),
                        author_email=author_obj.get("email"),
                        date=author_obj.get("date", ""),
                        html_url=c.get("html_url"),
                    )
                )
            if use_cache:
                _GITHUB_CACHE[cache_key] = (now, commits)
            return commits
        except GitHubRateLimitError:
            if cache_key in _GITHUB_CACHE:
                logger.warning("GitHub rate limit hit; serving cached commits for %s/%s", owner, repo)
                return _GITHUB_CACHE[cache_key][1]
            raise

    async def get_file_tree(
        self, owner: str, repo: str, tree_sha: str = "HEAD", recursive: bool = True
    ) -> List[GitHubTreeItem]:
        """Retrieve git tree for repository commit or branch."""
        params = {"recursive": "1"} if recursive else {}
        resp = await self._request("GET", f"/repos/{owner}/{repo}/git/trees/{tree_sha}", params=params)
        data = resp.json()

        tree_nodes = data.get("tree", [])
        items: List[GitHubTreeItem] = []
        for node in tree_nodes:
            if isinstance(node, dict):
                items.append(
                    GitHubTreeItem(
                        path=node["path"],
                        mode=node.get("mode", ""),
                        type=node.get("type", "blob"),
                        sha=node["sha"],
                        size=node.get("size"),
                    )
                )
        return items

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: Optional[str] = None
    ) -> GitHubFileContent:
        """Fetch raw contents of a single file in repository."""
        params = {"ref": ref} if ref else {}
        resp = await self._request("GET", f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}", params=params)
        data = resp.json()

        if isinstance(data, list):
            raise GitHubError(f"Path '{path}' is a directory, not a file.", status_code=400)

        encoding = data.get("encoding", "utf-8")
        raw_content = data.get("content", "")

        decoded_content: Optional[str] = None
        if encoding == "base64" and raw_content:
            try:
                decoded_bytes = base64.b64decode(raw_content)
                decoded_content = decoded_bytes.decode("utf-8", errors="replace")
            except Exception:
                decoded_content = None
        elif raw_content:
            decoded_content = raw_content

        return GitHubFileContent(
            path=data.get("path", path),
            sha=data.get("sha", ""),
            size=data.get("size", 0),
            encoding=encoding,
            content=decoded_content,
        )


def get_default_github_service() -> BaseGitHubService:
    """Return a GitHubService configured with the server-level token for worker/background tasks."""
    return GitHubService(token=settings.github_token)


async def get_github_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> BaseGitHubService:
    """
    FastAPI dependency that provides an authenticated GitHubService.
    Resolves the encrypted token stored for the current session.
    Falls back to settings.github_token if configured (Phase 2 backward compatibility).
    """
    session_id = request.cookies.get(settings.session_cookie_name) or request.headers.get("X-Session-ID")
    token: Optional[str] = None

    if session_id:
        stmt = select(GitHubConnection).where(GitHubConnection.session_identifier == session_id)
        result = await db.execute(stmt)
        conn = result.scalar_one_or_none()

        if conn and conn.access_token_encrypted:
            try:
                token = decrypt_token(conn.access_token_encrypted)
            except TokenDecryptionError:
                logger.warning("Failed to decrypt stored token for session %s", session_id[:8])

    # Fallback to server-level token if no session connection was found
    if not token and settings.github_token:
        token = settings.github_token

    return GitHubService(token=token)
