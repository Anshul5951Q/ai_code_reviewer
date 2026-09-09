from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import settings
from app.github.exceptions import (
    GitHubAuthError,
    GitHubError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
)

logger = logging.getLogger("ai_code_reviewer.github.client")


class GitHubHttpClient:
    """
    Low-level client for communicating with the GitHub REST API.
    Handles authentication headers, rate limit tracking, and structured exceptions.
    Ensures tokens are never logged or leaked.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.token = token
        self.base_url = (base_url or settings.github_api_base_url).rstrip("/")
        self._external_client = client

    def get_headers(self) -> Dict[str, str]:
        """Construct request headers. Never expose tokens in logs."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AICodeReviewer/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _extract_rate_limits(self, response: httpx.Response) -> Tuple[Optional[int], Optional[int], Optional[int]]:
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
        limit, remaining, _ = self._extract_rate_limits(response)

        # Check rate limit condition (429 or 403 with 0 remaining)
        if response.status_code == 429 or (
            response.status_code == 403 and remaining == 0
        ):
            logger.warning("GitHub rate limit reached: limit=%s, remaining=%s", limit, remaining)
            raise GitHubRateLimitError("GitHub API rate limit reached. Please try again later.")

        if response.status_code in (401, 403):
            logger.warning("GitHub authentication failed with status: %d", response.status_code)
            raise GitHubAuthError("GitHub authentication failed or insufficient repository permissions.")

        if response.status_code == 404:
            raise GitHubResourceNotFoundError("Requested GitHub repository or resource not found.")

        # Generic GitHub API error
        error_msg = f"GitHub API error (HTTP {response.status_code})"
        try:
            body = response.json()
            if isinstance(body, dict) and "message" in body:
                error_msg = f"GitHub API error: {body['message']}"
        except Exception:
            pass

        logger.error("GitHub API error: status=%d", response.status_code)
        raise GitHubError(error_msg, status_code=response.status_code)

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 15.0,
    ) -> httpx.Response:
        """Execute a GET request against the GitHub API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        req_headers = self.get_headers()
        if headers:
            req_headers.update(headers)

        async def _exec(client: httpx.AsyncClient) -> httpx.Response:
            return await client.get(url, headers=req_headers, params=params, timeout=timeout)

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
            raise GitHubError("Failed to connect to GitHub API. Please check your network connection.", status_code=502) from None

        if response.status_code >= 400:
            self._handle_error_response(response)

        return response
