"""
Re-export GitHub service and exceptions from app.github for backward compatibility.
All core logic is implemented in app.github.
"""
from __future__ import annotations

from app.github import (
    BaseGitHubService,
    GitHubAuthError,
    GitHubError,
    GitHubHttpClient,
    GitHubOAuthError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
    GitHubService,
    InvalidOAuthStateError,
    OAuthStateExpiredError,
    OAuthStateManager,
    exchange_code_for_token,
    get_authenticated_user_profile,
    get_authorization_url,
    get_github_service,
    get_default_github_service,
    oauth_state_manager,
    save_or_update_connection,
)

__all__ = [
    "BaseGitHubService",
    "GitHubService",
    "get_github_service",
    "get_default_github_service",
    "GitHubHttpClient",
    "GitHubError",
    "GitHubAuthError",
    "GitHubRateLimitError",
    "GitHubResourceNotFoundError",
    "GitHubOAuthError",
    "InvalidOAuthStateError",
    "OAuthStateExpiredError",
    "OAuthStateManager",
    "oauth_state_manager",
    "get_authorization_url",
    "exchange_code_for_token",
    "get_authenticated_user_profile",
    "save_or_update_connection",
]
