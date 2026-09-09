"""Tests for the health check endpoint."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_check_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_check_response_shape(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data


@pytest.mark.anyio
async def test_health_check_content_type(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert "application/json" in response.headers["content-type"]
