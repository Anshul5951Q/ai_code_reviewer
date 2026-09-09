from __future__ import annotations

import asyncio
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import encrypt_token
from app.github.exceptions import (
    GitHubAuthError,
    GitHubOAuthError,
    InvalidOAuthStateError,
    OAuthStateExpiredError,
)
from app.models.github_connection import GitHubConnection

logger = logging.getLogger("ai_code_reviewer.github.oauth")

# In-memory storage for active OAuth states: session_id -> (state, expire_timestamp)
_oauth_states: Dict[str, Tuple[str, float]] = {}
_state_lock = asyncio.Lock()


class OAuthStateManager:
    """
    Cryptographically secure OAuth state generator and validator.
    Ensures state is bound to the initiating session, expires after a TTL,
    and can only be used exactly once (protects against CSRF and replay attacks).
    """

    def __init__(self, ttl_seconds: int = 600) -> None:
        self.ttl_seconds = ttl_seconds

    async def create_state(self, session_id: str) -> str:
        """Generate and store a secure single-use state token bound to session_id."""
        state = secrets.token_urlsafe(32)
        expire_at = time.time() + self.ttl_seconds

        async with _state_lock:
            # Clean up any stale expired states
            now = time.time()
            stale_keys = [k for k, (_, exp) in _oauth_states.items() if exp < now]
            for k in stale_keys:
                _oauth_states.pop(k, None)

            _oauth_states[session_id] = (state, expire_at)

        return state

    async def validate_and_consume_state(self, session_id: str, state: str) -> None:
        """
        Validate that state matches the pending state for session_id and has not expired.
        Consumes the state immediately upon check so it cannot be replayed.
        Raises InvalidOAuthStateError or OAuthStateExpiredError on failure.
        """
        if not session_id or not state:
            raise InvalidOAuthStateError("Missing session identifier or OAuth state parameter.")

        async with _state_lock:
            entry = _oauth_states.pop(session_id, None)

        if not entry:
            logger.warning("OAuth state verification failed: no pending state found for session.")
            raise InvalidOAuthStateError("Authorization state could not be verified or was already used.")

        stored_state, expire_at = entry

        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(stored_state, state):
            logger.warning("OAuth state verification failed: state parameter mismatch.")
            raise InvalidOAuthStateError("Invalid authorization state.")

        if time.time() > expire_at:
            logger.warning("OAuth state verification failed: state expired.")
            raise OAuthStateExpiredError()


oauth_state_manager = OAuthStateManager(ttl_seconds=settings.oauth_state_ttl_seconds)


def get_authorization_url(state: str) -> str:
    """
    Generate the GitHub OAuth authorization URL with required parameters and minimal scopes.
    """
    client_id = settings.github_client_id
    if not client_id:
        logger.error("GITHUB_CLIENT_ID is not configured.")
        raise GitHubOAuthError(
            "GitHub OAuth is not configured on this server. Please contact your administrator.",
            status_code=503,
        )

    # Scopes: repository read access and basic user profile
    params = {
        "client_id": client_id,
        "redirect_uri": settings.github_redirect_uri,
        "scope": "repo,read:user",
        "state": state,
        "allow_signup": "true",
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


async def exchange_code_for_token(
    code: str,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """
    Exchange authorization code for access token via GitHub's OAuth endpoint.
    Never logs credentials or access tokens.
    """
    if not settings.github_client_id or not settings.github_client_secret:
        raise GitHubOAuthError(
            "GitHub OAuth credentials are not properly configured on server.",
            status_code=503,
        )

    url = "https://github.com/login/oauth/access_token"
    payload = {
        "client_id": settings.github_client_id,
        "client_secret": settings.github_client_secret,
        "code": code,
        "redirect_uri": settings.github_redirect_uri,
    }
    headers = {"Accept": "application/json"}

    async def _post(c: httpx.AsyncClient) -> httpx.Response:
        return await c.post(url, json=payload, headers=headers, timeout=15.0)

    try:
        if client:
            resp = await _post(client)
        else:
            async with httpx.AsyncClient() as default_client:
                resp = await _post(default_client)
    except Exception as exc:
        logger.error("Network failure communicating with GitHub OAuth server.")
        raise GitHubOAuthError(
            "Failed to contact GitHub authorization server. Please try again later.",
            status_code=502,
        ) from None

    if resp.status_code != 200:
        logger.error("GitHub token exchange returned HTTP status: %d", resp.status_code)
        raise GitHubOAuthError("GitHub token exchange failed.", status_code=resp.status_code)

    data = resp.json()
    if "error" in data:
        error_desc = data.get("error_description", data["error"])
        logger.warning("GitHub OAuth error returned from server: %s", data["error"])
        raise GitHubOAuthError(f"GitHub authorization failed: {error_desc}", status_code=400)

    access_token = data.get("access_token")
    if not access_token:
        raise GitHubOAuthError("No access token returned by GitHub.", status_code=400)

    return {
        "access_token": access_token,
        "token_type": data.get("token_type", "bearer"),
        "scope": data.get("scope", ""),
    }


async def get_authenticated_user_profile(
    token: str,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """
    Retrieve user ID, login, and avatar URL using the given access token.
    Never logs or exposes the token.
    """
    url = f"{settings.github_api_base_url.rstrip('/')}/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AICodeReviewer/1.0",
    }

    async def _get(c: httpx.AsyncClient) -> httpx.Response:
        return await c.get(url, headers=headers, timeout=10.0)

    try:
        if client:
            resp = await _get(client)
        else:
            async with httpx.AsyncClient() as default_client:
                resp = await _get(default_client)
    except Exception:
        raise GitHubOAuthError("Failed to fetch user profile from GitHub.", status_code=502) from None

    if resp.status_code == 401:
        raise GitHubAuthError("GitHub access token is invalid or expired.")
    if resp.status_code != 200:
        raise GitHubOAuthError("Unable to retrieve authenticated GitHub user profile.", status_code=resp.status_code)

    data = resp.json()
    return {
        "id": data.get("id"),
        "login": data.get("login"),
        "avatar_url": data.get("avatar_url"),
        "name": data.get("name"),
    }


async def save_or_update_connection(
    db: AsyncSession,
    session_id: str,
    token_data: dict,
    user_profile: dict,
) -> GitHubConnection:
    """
    Store or update an encrypted GitHub connection for the current session.
    Token is encrypted at rest using server-side encryption.
    """
    encrypted_token = encrypt_token(token_data["access_token"])
    now = datetime.now(timezone.utc)

    # Check for existing connection for this session
    stmt = select(GitHubConnection).where(GitHubConnection.session_identifier == session_id)
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()

    if connection is None:
        connection = GitHubConnection(
            session_identifier=session_id,
            github_user_id=user_profile["id"],
            github_login=user_profile["login"],
            github_avatar_url=user_profile.get("avatar_url"),
            access_token_encrypted=encrypted_token,
            token_type=token_data.get("token_type", "bearer"),
            scope=token_data.get("scope"),
            last_verified_at=now,
        )
        db.add(connection)
    else:
        connection.github_user_id = user_profile["id"]
        connection.github_login = user_profile["login"]
        connection.github_avatar_url = user_profile.get("avatar_url")
        connection.access_token_encrypted = encrypted_token
        connection.token_type = token_data.get("token_type", "bearer")
        connection.scope = token_data.get("scope")
        connection.last_verified_at = now

    await db.commit()
    await db.refresh(connection)
    logger.info("GitHub connection saved successfully for login: %s", connection.github_login)
    return connection
