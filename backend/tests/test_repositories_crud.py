"""Tests for real database-backed repository CRUD operations."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_repository_lifecycle_crud(client: AsyncClient) -> None:
    # 1. Initially empty
    list_res = await client.get("/api/repositories")
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 0
    assert list_res.json()["items"] == []

    # 2. Create repository
    payload = {
        "name": "react-flow",
        "full_name": "xyflow/react-flow",
        "owner": "xyflow",
        "default_branch": "main",
        "visibility": "public",
        "language": "TypeScript",
        "github_id": 998877,
    }
    create_res = await client.post("/api/repositories", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["full_name"] == "xyflow/react-flow"
    assert created["owner"] == "xyflow"
    repo_id = created["id"]

    # 3. Prevent duplicate creation
    dup_res = await client.post("/api/repositories", json=payload)
    assert dup_res.status_code == 409

    # 4. Get repository by ID
    get_res = await client.get(f"/api/repositories/{repo_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == repo_id
    assert get_res.json()["name"] == "react-flow"

    # 5. List repositories and verify presence
    list_res2 = await client.get("/api/repositories")
    assert list_res2.status_code == 200
    assert list_res2.json()["total"] == 1
    assert list_res2.json()["items"][0]["id"] == repo_id

    # 6. Search filtering
    match_search = await client.get("/api/repositories?q=react")
    assert match_search.status_code == 200
    assert match_search.json()["total"] == 1

    no_match_search = await client.get("/api/repositories?q=nonexistentquery")
    assert no_match_search.status_code == 200
    assert no_match_search.json()["total"] == 0

    # 7. Delete repository
    del_res = await client.delete(f"/api/repositories/{repo_id}")
    assert del_res.status_code == 204

    # 8. Verify 404 after deletion
    get_del = await client.get(f"/api/repositories/{repo_id}")
    assert get_del.status_code == 404


@pytest.mark.anyio
async def test_repository_pagination(client: AsyncClient) -> None:
    # Create 3 repositories
    for i in range(3):
        await client.post(
            "/api/repositories",
            json={
                "name": f"service-{i}",
                "full_name": f"org/service-{i}",
                "owner": "org",
                "default_branch": "main",
                "visibility": "private",
            },
        )

    # Test limit=2, offset=0
    page1 = await client.get("/api/repositories?limit=2&offset=0")
    assert page1.status_code == 200
    data1 = page1.json()
    assert data1["total"] == 3
    assert len(data1["items"]) == 2

    # Test limit=2, offset=2
    page2 = await client.get("/api/repositories?limit=2&offset=2")
    assert page2.status_code == 200
    data2 = page2.json()
    assert data2["total"] == 3
    assert len(data2["items"]) == 1


@pytest.mark.anyio
async def test_repository_not_found(client: AsyncClient) -> None:
    res = await client.get("/api/repositories/non-existent-uuid")
    assert res.status_code == 404

    del_res = await client.delete("/api/repositories/non-existent-uuid")
    assert del_res.status_code == 404
