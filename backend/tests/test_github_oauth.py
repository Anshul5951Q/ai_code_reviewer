"""Unit and integration tests for GitHub OAuth flow and state security."""
from __future__ import annotations

import time
import pytest
from httpx import AsyncClient, MockTransport, Response, Request

from app.core.config import settings
from app.github.exceptions import (
    GitHubAuthError,
    GitHubOAuthError,
    InvalidOAuthStateError,
    OAuthStateExpiredError,
)
from app.github.oauth import (
    OAuthStateManager,
    exchange_code_for_token,
    get_authenticated_user_profile,
    get_authorization_url,
    oauth_state_manager,
)


# ---------------------------------------------------------------------------
# State Manager Unit Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_oauth_state_manager_create_and_validate():
    """State should be created and successfully validated once."""
    mgr = OAuthStateManager(ttl_seconds=300)
    session_id = "test-session-123"

    state = await mgr.create_state(session_id)
    assert len(state) >= 32

    # First validation succeeds
    await mgr.validate_and_consume_state(session_id, state)


@pytest.mark.anyio
async def test_oauth_state_cannot_be_replayed():
    """Validating state consumes it; second validation must fail."""
    mgr = OAuthStateManager(ttl_seconds=300)
    session_id = "test-session-replay"

    state = await mgr.create_state(session_id)
    await mgr.validate_and_consume_state(session_id, state)

    # Second validation must raise InvalidOAuthStateError
    with pytest.raises(InvalidOAuthStateError):
        await mgr.validate_and_consume_state(session_id, state)


@pytest.mark.anyio
async def test_oauth_state_mismatch_rejected():
    """Tampered or incorrect state is rejected."""
    mgr = OAuthStateManager(ttl_seconds=300)
    session_id = "test-session-mismatch"

    await mgr.create_state(session_id)

    with pytest.raises(InvalidOAuthStateError):
        await mgr.validate_and_consume_state(session_id, "wrong-state-value")


@pytest.mark.anyio
async def test_oauth_state_expired_rejected():
    """State past its TTL is rejected with OAuthStateExpiredError."""
    # Create manager with immediate expiration
    mgr = OAuthStateManager(ttl_seconds=-1)
    session_id = "test-session-expired"

    state = await mgr.create_state(session_id)

    with pytest.raises(OAuthStateExpiredError):
        await mgr.validate_and_consume_state(session_id, state)


# ---------------------------------------------------------------------------
# Authorization URL
# ---------------------------------------------------------------------------

def test_get_authorization_url():
    """Authorization URL should have required query parameters and minimal scopes."""
    settings.github_client_id = "test-client-id"
    url = get_authorization_url("secure-state-token-123")

    assert "https://github.com/login/oauth/authorize" in url
    assert "client_id=test-client-id" in url
    assert "state=secure-state-token-123" in url
    assert "scope=repo%2Cread%3Auser" in url or "scope=repo" in url


# ---------------------------------------------------------------------------
# Token Exchange & User Profile (Mocked HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_exchange_code_for_token_success():
    """Code exchange contacts GitHub and returns token data."""
    settings.github_client_id = "test-client-id"
    settings.github_client_secret = "test-client-secret"

    def handler(request: Request) -> Response:
        assert request.url.path == "/login/oauth/access_token"
        return Response(
            200,
            json={
                "access_token": "gho_testtoken987",
                "token_type": "bearer",
                "scope": "repo,read:user",
            },
        )

    mock_client = AsyncClient(transport=MockTransport(handler))
    token_data = await exchange_code_for_token("test-code-123", client=mock_client)

    assert token_data["access_token"] == "gho_testtoken987"
    assert token_data["token_type"] == "bearer"


@pytest.mark.anyio
async def test_exchange_code_for_token_github_error():
    """GitHub returning error in JSON response raises GitHubOAuthError."""
    settings.github_client_id = "test-client-id"
    settings.github_client_secret = "test-client-secret"

    def handler(request: Request) -> Response:
        return Response(
            200,
            json={
                "error": "bad_verification_code",
                "error_description": "The code passed is incorrect or expired.",
            },
        )

    mock_client = AsyncClient(transport=MockTransport(handler))
    with pytest.raises(GitHubOAuthError) as exc_info:
        await exchange_code_for_token("invalid-code", client=mock_client)

    assert "incorrect or expired" in exc_info.value.message


@pytest.mark.anyio
async def test_get_authenticated_user_profile():
    """User profile fetch retrieves login and avatar."""
    def handler(request: Request) -> Response:
        assert "Bearer gho_mytoken" in request.headers.get("Authorization", "")
        return Response(
            200,
            json={
                "id": 123456,
                "login": "octocat-dev",
                "avatar_url": "https://avatars.githubusercontent.com/u/123456",
                "name": "Octocat Developer",
            },
        )

    mock_client = AsyncClient(transport=MockTransport(handler))
    profile = await get_authenticated_user_profile("gho_mytoken", client=mock_client)

    assert profile["id"] == 123456
    assert profile["login"] == "octocat-dev"
    assert profile["avatar_url"] == "https://avatars.githubusercontent.com/u/123456"


# ---------------------------------------------------------------------------
# OAuth Endpoint Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_connect_github_redirects_and_sets_cookie(client: AsyncClient):
    """GET /api/github/connect sets session cookie and returns 307 redirect."""
    settings.github_client_id = "mock-client-id"
    res = await client.get("/api/github/connect", follow_redirects=False)

    assert res.status_code == 307
    location = res.headers.get("location", "")
    assert "https://github.com/login/oauth/authorize" in location
    assert "state=" in location

    # Cookie was set
    cookie_header = res.headers.get("set-cookie", "")
    assert settings.session_cookie_name in cookie_header


@pytest.mark.anyio
async def test_callback_cancelled_by_user(client: AsyncClient):
    """Callback with error=access_denied redirects to ?github=cancelled."""
    res = await client.get(
        "/api/github/callback?error=access_denied&error_description=The+user+cancelled",
        follow_redirects=False,
    )
    assert res.status_code == 307
    assert "github=cancelled" in res.headers.get("location", "")


@pytest.mark.anyio
async def test_callback_invalid_state_redirects(client: AsyncClient):
    """Callback without valid state redirects to ?github=invalid_state."""
    res = await client.get(
        "/api/github/callback?code=mock-code&state=non-existent-state",
        follow_redirects=False,
    )
    assert res.status_code == 307
    assert "github=invalid_state" in res.headers.get("location", "")


@pytest.mark.anyio
async def test_connect_github_unconfigured_redirects_to_frontend_error(client: AsyncClient):
    """When GitHub OAuth is unconfigured, /api/github/connect redirects gracefully to frontend error."""
    settings.github_client_id = ""
    res = await client.get("/api/github/connect", follow_redirects=False)
    assert res.status_code == 307
    location = res.headers.get("location", "")
    assert "dashboard/repositories?github=error" in location


@pytest.mark.anyio
async def test_connect_github_token_success(client: AsyncClient, monkeypatch):
    """POST /api/github/connect-token with valid token connects account and sets cookie."""
    async def mock_get_profile(token: str, client=None):
        return {
            "id": 99999,
            "login": "octocat-tester",
            "avatar_url": "https://avatars.githubusercontent.com/u/99999",
            "name": "Octocat Tester",
        }

    async def mock_verify(self):
        from app.schemas.github import GitHubStatusResponse
        return GitHubStatusResponse(
            connected=True,
            github_login="octocat-tester",
            avatar_url="https://avatars.githubusercontent.com/u/99999",
            authenticated_user="octocat-tester",
            user_name="Octocat Tester",
            scopes=["repo", "read:user"],
            rate_limit_limit=5000,
            rate_limit_remaining=4999,
        )

    monkeypatch.setattr("app.api.github.get_authenticated_user_profile", mock_get_profile)
    from app.github.service import GitHubService
    monkeypatch.setattr(GitHubService, "verify_connection", mock_verify)

    res = await client.post("/api/github/connect-token", json={"token": "ghp_validmocktoken1234567890"})
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is True
    assert data["github_login"] == "octocat-tester"
    cookie_header = res.headers.get("set-cookie", "")
    assert settings.session_cookie_name in cookie_header


@pytest.mark.anyio
async def test_connect_github_token_invalid(client: AsyncClient, monkeypatch):
    """POST /api/github/connect-token with invalid token returns 401."""
    async def mock_get_profile(token: str, client=None):
        raise GitHubAuthError("Bad credentials")

    monkeypatch.setattr("app.api.github.get_authenticated_user_profile", mock_get_profile)

    res = await client.post("/api/github/connect-token", json={"token": "ghp_invalidbadtoken123"})
    assert res.status_code == 401
    assert "Invalid GitHub token" in res.json()["detail"]

