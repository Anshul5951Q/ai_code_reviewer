"""Tests for Analysis Job API endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_repo(client: AsyncClient) -> str:
    """Create a test repository and return its ID."""
    resp = await client.post(
        "/api/repositories",
        json={
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "owner": "owner",
            "default_branch": "main",
            "visibility": "public",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_review(client: AsyncClient, repo_id: str) -> str:
    """Create a test review and return its ID."""
    resp = await client.post(
        "/api/reviews",
        json={
            "repository_id": repo_id,
            "commit_sha": "abc1234567890123456789012345678901234567",
            "branch": "main",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# POST /reviews/{id}/analyze
# ---------------------------------------------------------------------------

class TestStartAnalysis:
    async def test_start_analysis_returns_202(self, client: AsyncClient):
        repo_id = await create_repo(client)
        review_id = await create_review(client, repo_id)
        resp = await client.post(f"/api/reviews/{review_id}/analyze")
        assert resp.status_code == 202

    async def test_start_analysis_returns_job_id(self, client: AsyncClient):
        repo_id = await create_repo(client)
        review_id = await create_review(client, repo_id)
        resp = await client.post(f"/api/reviews/{review_id}/analyze")
        data = resp.json()
        assert "job_id" in data
        assert len(data["job_id"]) == 36  # UUID

    async def test_start_analysis_review_not_found(self, client: AsyncClient):
        resp = await client.post("/api/reviews/nonexistent-id/analyze")
        assert resp.status_code == 404

    async def test_idempotent_second_call_returns_existing_job(self, client: AsyncClient):
        repo_id = await create_repo(client)
        review_id = await create_review(client, repo_id)
        resp1 = await client.post(f"/api/reviews/{review_id}/analyze")
        resp2 = await client.post(f"/api/reviews/{review_id}/analyze")
        assert resp1.status_code == 202
        assert resp2.status_code == 202
        # Second call returns the existing job
        assert resp1.json()["job_id"] == resp2.json()["job_id"]

    async def test_start_analysis_status_is_queued(self, client: AsyncClient):
        repo_id = await create_repo(client)
        review_id = await create_review(client, repo_id)
        resp = await client.post(f"/api/reviews/{review_id}/analyze")
        assert resp.json()["status"] == "queued"


# ---------------------------------------------------------------------------
# GET /reviews/{id}/analysis
# ---------------------------------------------------------------------------

class TestGetAnalysisStatus:
    async def test_status_returns_404_without_job(self, client: AsyncClient):
        repo_id = await create_repo(client)
        review_id = await create_review(client, repo_id)
        resp = await client.get(f"/api/reviews/{review_id}/analysis")
        assert resp.status_code == 404

    async def test_status_returns_job_after_start(self, client: AsyncClient):
        repo_id = await create_repo(client)
        review_id = await create_review(client, repo_id)
        await client.post(f"/api/reviews/{review_id}/analyze")
        resp = await client.get(f"/api/reviews/{review_id}/analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_id"] == review_id
        assert data["status"] == "queued"
        assert data["progress"] == 0.0
        assert data["files_total"] == 0
        assert data["files_processed"] == 0

    async def test_status_review_not_found(self, client: AsyncClient):
        resp = await client.get("/api/reviews/nonexistent-id/analysis")
        assert resp.status_code == 404

    async def test_status_contains_required_fields(self, client: AsyncClient):
        repo_id = await create_repo(client)
        review_id = await create_review(client, repo_id)
        await client.post(f"/api/reviews/{review_id}/analyze")
        resp = await client.get(f"/api/reviews/{review_id}/analysis")
        data = resp.json()
        required = {"id", "review_id", "status", "progress", "files_total", "files_processed", "created_at", "updated_at"}
        assert required.issubset(data.keys())


# ---------------------------------------------------------------------------
# GET /reviews/{id}/snapshot
# ---------------------------------------------------------------------------

class TestGetSnapshot:
    async def test_snapshot_returns_404_before_completion(self, client: AsyncClient):
        repo_id = await create_repo(client)
        review_id = await create_review(client, repo_id)
        resp = await client.get(f"/api/reviews/{review_id}/snapshot")
        assert resp.status_code == 404

    async def test_snapshot_review_not_found(self, client: AsyncClient):
        resp = await client.get("/api/reviews/nonexistent-id/snapshot")
        assert resp.status_code == 404
