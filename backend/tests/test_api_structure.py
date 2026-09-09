"""Tests for API route structure — verifies endpoints exist and return correct response shapes."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_repositories_returns_empty_list(client: AsyncClient) -> None:
    response = await client.get("/api/repositories")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 0
    assert data["total"] == 0


@pytest.mark.anyio
async def test_repository_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/repositories/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_reviews_returns_empty_list(client: AsyncClient) -> None:
    response = await client.get("/api/reviews")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 0
    assert data["total"] == 0


@pytest.mark.anyio
async def test_review_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/reviews/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_security_summary_returns_zeroed_data(client: AsyncClient) -> None:
    response = await client.get("/api/security/summary")
    assert response.status_code == 200
    data = response.json()
    assert "critical_count" in data
    assert "high_count" in data
    assert "medium_count" in data
    assert "low_count" in data
    assert data["critical_count"] == 0
    assert data["repositories_analyzed"] == 0


@pytest.mark.anyio
async def test_security_findings_returns_empty_list(client: AsyncClient) -> None:
    response = await client.get("/api/security/findings")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total"] == 0


@pytest.mark.anyio
async def test_openapi_schema_accessible(client: AsyncClient) -> None:
    response = await client.get("/api/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "paths" in schema
