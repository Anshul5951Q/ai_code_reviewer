"""Tests for GitHub connection model, status, disconnect, and token privacy."""
from __future__ import annotations

import pytest
from httpx import AsyncClient, MockTransport, Response, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import decrypt_token, encrypt_token
from app.models.github_connection import GitHubConnection


@pytest.mark.anyio
async def test_github_connection_stores_encrypted_token(db_session: AsyncSession):
    """Database column access_token_encrypted must NOT store plaintext token."""
    raw_token = "gho_plaintext_secret_token_12345"
    encrypted = encrypt_token(raw_token)

    conn = GitHubConnection(
        session_identifier="session-xyz-1",
        github_user_id=98765,
        github_login="secure-user",
        github_avatar_url="https://example.com/avatar.png",
        access_token_encrypted=encrypted,
    )
    db_session.add(conn)
    await db_session.commit()

    # Query from DB directly
    stmt = select(GitHubConnection).where(GitHubConnection.session_identifier == "session-xyz-1")
    result = await db_session.execute(stmt)
    persisted = result.scalar_one()

    # Plaintext token is NOT in database
    assert raw_token not in persisted.access_token_encrypted
    assert persisted.access_token_encrypted != raw_token

    # Decrypting returns the original token
    assert decrypt_token(persisted.access_token_encrypted) == raw_token

    # __repr__ does NOT leak token
    repr_str = repr(persisted)
    assert raw_token not in repr_str
    assert "token" not in repr_str.lower() or "secret" not in repr_str.lower()


@pytest.mark.anyio
async def test_status_disconnected(client: AsyncClient):
    """GET /api/github/status without credentials or token reports connected=False."""
    # Temporarily ensure settings.github_token is None
    original_token = settings.github_token
    settings.github_token = None
    try:
        res = await client.get("/api/github/status")
        assert res.status_code == 200
        data = res.json()
        assert data["connected"] is False
    finally:
        settings.github_token = original_token


@pytest.mark.anyio
async def test_status_and_disconnect_flow(client: AsyncClient, db_session: AsyncSession):
    """Test full connection lifecycle: connected -> status -> disconnect -> status disconnected."""
    session_id = "test-session-lifecycle"
    raw_token = "gho_test_user_token_abc"
    encrypted = encrypt_token(raw_token)

    # 1. Store connection in DB
    conn = GitHubConnection(
        session_identifier=session_id,
        github_user_id=12345,
        github_login="active-coder",
        github_avatar_url="https://avatars.githubusercontent.com/u/12345",
        access_token_encrypted=encrypted,
    )
    db_session.add(conn)
    await db_session.commit()

    # Mock GitHub API for the status call
    def handler(request: Request) -> Response:
        if request.url.path == "/user":
            return Response(200, json={"login": "active-coder", "name": "Active Coder"})
        if request.url.path == "/rate_limit":
            return Response(200, json={"resources": {"core": {"limit": 5000, "remaining": 4900, "reset": 1700000000}}})
        return Response(404)

    # Set session cookie in client
    client.cookies.set(settings.session_cookie_name, session_id)

    # 2. Check status
    from app.services.github import GitHubService, get_github_service
    from app.main import app
    import httpx

    mock_client = httpx.AsyncClient(transport=MockTransport(handler))
    mock_service = GitHubService(token=raw_token, client=mock_client)
    app.dependency_overrides[get_github_service] = lambda: mock_service

    try:
        res = await client.get("/api/github/status")
        assert res.status_code == 200
        data = res.json()
        assert data["connected"] is True
        assert data["github_login"] == "active-coder"
        assert data["rate_limit_remaining"] == 4900

        # Security check: Token must NEVER appear in JSON response
        response_text = res.text
        assert raw_token not in response_text
        assert "gho_" not in response_text
    finally:
        app.dependency_overrides.pop(get_github_service, None)

    # 3. Disconnect
    del_res = await client.delete("/api/github/connection")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["disconnected"] is True

    # 4. Verify record was removed from DB
    stmt = select(GitHubConnection).where(GitHubConnection.session_identifier == session_id)
    persisted = (await db_session.execute(stmt)).scalar_one_or_none()
    assert persisted is None
