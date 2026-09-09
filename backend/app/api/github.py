from __future__ import annotations

import logging
import secrets
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.github.exceptions import (
    GitHubAuthError,
    GitHubError,
    GitHubOAuthError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
    InvalidOAuthStateError,
    OAuthStateExpiredError,
)
from app.github.oauth import (
    exchange_code_for_token,
    get_authenticated_user_profile,
    get_authorization_url,
    oauth_state_manager,
    save_or_update_connection,
)
from app.github.service import BaseGitHubService, GitHubService, get_github_service
from app.models.github_connection import GitHubConnection
from app.schemas.github import (
    GitHubBranch,
    GitHubCommit,
    GitHubDisconnectResponse,
    GitHubFileContent,
    GitHubRepoItem,
    GitHubStatusResponse,
    GitHubTokenConnectRequest,
    GitHubTreeItem,
)

logger = logging.getLogger("ai_code_reviewer.api.github")

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/connect")
async def connect_github(
    request: Request,
    response: Response,
) -> RedirectResponse:
    """
    Initiate GitHub OAuth Authorization Code flow.
    Generates single-use CSRF state, binds it to session cookie, and redirects to GitHub.
    """
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        session_id = secrets.token_urlsafe(24)

    state = await oauth_state_manager.create_state(session_id)

    try:
        auth_url = get_authorization_url(state)
    except GitHubOAuthError as e:
        # Gracefully redirect to frontend with error message so browser does not display raw JSON error page
        frontend_base = settings.frontend_url.rstrip("/")
        safe_msg = quote(e.message)
        return RedirectResponse(
            url=f"{frontend_base}/dashboard/repositories?github=error&message={safe_msg}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    redirect_resp = RedirectResponse(
        url=auth_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
    redirect_resp.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=30 * 86400,  # 30 days
    )
    return redirect_resp


@router.get("/callback")
async def github_callback(
    request: Request,
    code: Optional[str] = Query(None, description="GitHub authorization code"),
    state: Optional[str] = Query(None, description="OAuth CSRF state token"),
    error: Optional[str] = Query(None, description="GitHub error code"),
    error_description: Optional[str] = Query(None, description="GitHub error description"),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """
    Handle GitHub OAuth callback.
    Validates CSRF state, exchanges code for access token, retrieves user, encrypts and stores token.
    Redirects back to frontend with status.
    """
    frontend_base = settings.frontend_url.rstrip("/")

    # Handle user cancellation on GitHub authorization page
    if error == "access_denied" or error == "user_cancelled":
        logger.info("GitHub OAuth was cancelled by user.")
        return RedirectResponse(
            url=f"{frontend_base}/dashboard/repositories?github=cancelled",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    if error:
        logger.warning("GitHub OAuth callback returned error: %s - %s", error, error_description)
        safe_msg = quote(error_description or error or "Authorization failed")
        return RedirectResponse(
            url=f"{frontend_base}/dashboard/repositories?github=error&message={safe_msg}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id or not state or not code:
        logger.warning("OAuth callback missing session_id, state, or code.")
        return RedirectResponse(
            url=f"{frontend_base}/dashboard/repositories?github=invalid_state",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # Validate and consume state token (one-time use)
    try:
        await oauth_state_manager.validate_and_consume_state(session_id, state)
    except (InvalidOAuthStateError, OAuthStateExpiredError) as exc:
        logger.warning("OAuth state verification failed: %s", exc)
        return RedirectResponse(
            url=f"{frontend_base}/dashboard/repositories?github=invalid_state",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # Exchange code for token
    try:
        token_data = await exchange_code_for_token(code)
    except GitHubOAuthError as exc:
        logger.error("Token exchange failed during callback: %s", exc.message)
        safe_msg = quote(exc.message)
        return RedirectResponse(
            url=f"{frontend_base}/dashboard/repositories?github=error&message={safe_msg}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # Fetch authenticated user profile
    try:
        user_profile = await get_authenticated_user_profile(token_data["access_token"])
    except (GitHubAuthError, GitHubOAuthError) as exc:
        logger.error("User profile fetch failed: %s", exc.message)
        return RedirectResponse(
            url=f"{frontend_base}/dashboard/repositories?github=error&message=profile_fetch_failed",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # Encrypt token and persist connection
    await save_or_update_connection(
        db=db,
        session_id=session_id,
        token_data=token_data,
        user_profile=user_profile,
    )

    return RedirectResponse(
        url=f"{frontend_base}/dashboard/repositories?github=connected",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/status", response_model=GitHubStatusResponse)
async def get_github_status(
    github_service: BaseGitHubService = Depends(get_github_service),
) -> GitHubStatusResponse:
    """
    Check current GitHub connection status for the requesting session.
    Never returns credentials or tokens.
    """
    status_resp = await github_service.verify_connection()
    status_resp.oauth_configured = bool(settings.github_client_id and settings.github_client_secret)
    return status_resp


@router.post("/connect-token", response_model=GitHubStatusResponse)
async def connect_github_token(
    payload: GitHubTokenConnectRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> GitHubStatusResponse:
    """
    Connect a GitHub account directly using a Personal Access Token (PAT).
    Validates the token against GitHub API, securely encrypts it, and saves the connection.
    """
    raw_token = payload.token.strip()
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token cannot be empty.")

    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        session_id = secrets.token_urlsafe(24)

    # Validate token against GitHub API and fetch profile
    try:
        user_profile = await get_authenticated_user_profile(raw_token)
    except GitHubAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub token. Please verify that your token is active and has 'repo' and 'read:user' permissions.",
        )
    except Exception as exc:
        logger.error("Failed to verify token with GitHub: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to contact GitHub API. Please check your network connection.",
        )

    token_data = {
        "access_token": raw_token,
        "token_type": "bearer",
        "scope": "repo,read:user",
    }

    await save_or_update_connection(
        db=db,
        session_id=session_id,
        token_data=token_data,
        user_profile=user_profile,
    )

    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=30 * 86400,
    )

    service = GitHubService(token=raw_token)
    status_resp = await service.verify_connection()
    status_resp.oauth_configured = bool(settings.github_client_id and settings.github_client_secret)
    return status_resp


@router.delete("/connection", response_model=GitHubDisconnectResponse)
async def disconnect_github(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> GitHubDisconnectResponse:
    """
    Disconnect GitHub account for the current session.
    Removes encrypted token data from database.
    Does NOT delete imported repository records or reviews.
    """
    session_id = request.cookies.get(settings.session_cookie_name) or request.headers.get("X-Session-ID")

    if session_id:
        stmt = delete(GitHubConnection).where(GitHubConnection.session_identifier == session_id)
        await db.execute(stmt)
        await db.commit()

    return GitHubDisconnectResponse(
        disconnected=True,
        message="GitHub connection removed successfully.",
    )


@router.get("/repositories", response_model=List[GitHubRepoItem])
async def list_github_repositories(
    response: Response,
    limit: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    type: Optional[str] = Query(None, description="Filter: all, owner, member, public, private"),
    visibility: Optional[str] = Query(None, description="Filter: all, public, private"),
    affiliation: Optional[str] = Query(None, description="Filter: owner, collaborator, organization_member"),
    q: Optional[str] = Query(None, description="Search term to filter repositories"),
    github_service: BaseGitHubService = Depends(get_github_service),
) -> List[GitHubRepoItem]:
    """List remote repositories accessible to the current GitHub connection with pagination and filters."""
    try:
        import inspect
        sig = inspect.signature(github_service.list_repositories)
        call_kwargs: dict[str, Any] = {"limit": limit}
        if "page" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            call_kwargs.update({
                "page": page,
                "repo_type": type,
                "visibility": visibility,
                "affiliation": affiliation,
                "search": q,
            })

        repos = await github_service.list_repositories(**call_kwargs)
        response.headers["X-Page"] = str(page)
        response.headers["X-Per-Page"] = str(limit)
        response.headers["X-Has-More"] = "true" if len(repos) == limit else "false"
        return repos
    except GitHubRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.get("/branches", response_model=List[GitHubBranch])
async def list_github_branches(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    github_service: BaseGitHubService = Depends(get_github_service),
) -> List[GitHubBranch]:
    """List branches for a GitHub repository."""
    try:
        return await github_service.list_branches(owner=owner, repo=repo)
    except GitHubResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitHubRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.get("/commits", response_model=List[GitHubCommit])
async def list_github_commits(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    branch: Optional[str] = Query(None, description="Branch name or commit SHA"),
    limit: int = Query(30, ge=1, le=100),
    github_service: BaseGitHubService = Depends(get_github_service),
) -> List[GitHubCommit]:
    """List commits for a GitHub repository branch."""
    try:
        return await github_service.list_commits(
            owner=owner, repo=repo, branch=branch, limit=limit
        )
    except GitHubResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitHubRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.get("/tree", response_model=List[GitHubTreeItem])
async def get_github_tree(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    tree_sha: str = Query("HEAD", description="Commit SHA or branch"),
    recursive: bool = Query(True, description="Recursively list file tree"),
    github_service: BaseGitHubService = Depends(get_github_service),
) -> List[GitHubTreeItem]:
    """Retrieve file tree for a repository."""
    try:
        return await github_service.get_file_tree(
            owner=owner, repo=repo, tree_sha=tree_sha, recursive=recursive
        )
    except GitHubResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitHubRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.get("/content", response_model=GitHubFileContent)
async def get_github_content(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    path: str = Query(..., description="Path to file in repository"),
    ref: Optional[str] = Query(None, description="Branch or commit SHA"),
    github_service: BaseGitHubService = Depends(get_github_service),
) -> GitHubFileContent:
    """Retrieve source code contents of a file."""
    try:
        return await github_service.get_file_content(
            owner=owner, repo=repo, path=path, ref=ref
        )
    except GitHubResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitHubRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
