from __future__ import annotations


class GitHubError(Exception):
    """Base exception for GitHub service errors."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GitHubAuthError(GitHubError):
    """GitHub authentication or permission error."""

    def __init__(self, message: str = "GitHub authentication failed") -> None:
        super().__init__(message, status_code=401)


class GitHubRateLimitError(GitHubError):
    """GitHub API rate limit exceeded."""

    def __init__(self, message: str = "GitHub API rate limit exceeded") -> None:
        super().__init__(message, status_code=429)


class GitHubResourceNotFoundError(GitHubError):
    """GitHub repository, branch, commit, or file not found."""

    def __init__(self, message: str = "Requested GitHub resource not found") -> None:
        super().__init__(message, status_code=404)


class GitHubOAuthError(GitHubError):
    """Error encountered during GitHub OAuth handshake or token exchange."""

    def __init__(self, message: str = "GitHub OAuth error", status_code: int = 400) -> None:
        super().__init__(message, status_code=status_code)


class InvalidOAuthStateError(GitHubOAuthError):
    """Provided OAuth state parameter is missing, invalid, or mismatched."""

    def __init__(self, message: str = "GitHub authorization state could not be verified") -> None:
        super().__init__(message, status_code=400)


class OAuthStateExpiredError(GitHubOAuthError):
    """Provided OAuth state parameter has expired."""

    def __init__(self, message: str = "GitHub authorization session has expired. Please restart the connection.") -> None:
        super().__init__(message, status_code=400)
