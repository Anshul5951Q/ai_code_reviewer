from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class GitHubStatusResponse(BaseModel):
    """GitHub integration connection status."""
    connected: bool
    github_login: Optional[str] = None
    avatar_url: Optional[str] = None
    last_verified_at: Optional[str] = None
    # Backward-compatible fields
    authenticated_user: Optional[str] = None
    user_name: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    rate_limit_limit: Optional[int] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[int] = None
    error: Optional[str] = None
    oauth_configured: bool = False


class GitHubTokenConnectRequest(BaseModel):
    """Payload for connecting via GitHub Personal Access Token."""
    token: str = Field(..., min_length=4, description="GitHub Personal Access Token or OAuth token")


class GitHubDisconnectResponse(BaseModel):
    """Response returned upon disconnecting GitHub account."""
    disconnected: bool = True
    message: str = "GitHub connection removed successfully."


class GitHubRepoItem(BaseModel):
    """Remote GitHub repository item."""
    id: int
    name: str
    full_name: str
    owner: str
    html_url: str
    default_branch: str = "main"
    visibility: str = "public"
    language: Optional[str] = None
    description: Optional[str] = None
    updated_at: Optional[str] = None


class GitHubBranch(BaseModel):
    """GitHub branch item."""
    name: str
    commit_sha: str
    protected: bool = False


class GitHubCommit(BaseModel):
    """GitHub commit item with formatted metadata."""
    sha: str
    short_sha: str
    message: str
    author_name: str
    author_email: Optional[str] = None
    date: str
    html_url: Optional[str] = None


class GitHubTreeItem(BaseModel):
    """File or folder node in git tree."""
    path: str
    mode: str
    type: str  # blob or tree
    sha: str
    size: Optional[int] = None


class GitHubFileContent(BaseModel):
    """Retrieved file content from GitHub repository."""
    path: str
    sha: str
    size: int
    encoding: str
    content: Optional[str] = None
