from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.repository import Repository
from app.schemas.github import (
    GitHubBranch,
    GitHubCommit,
    GitHubFileContent,
    GitHubTreeItem,
)
from app.schemas.repository import (
    RepositoryCreate,
    RepositoryListResponse,
    RepositoryResponse,
)
from app.services.github import (
    BaseGitHubService,
    GitHubAuthError,
    GitHubError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
    get_github_service,
)

router = APIRouter(tags=["repositories"])


@router.get("/repositories", response_model=RepositoryListResponse)
async def list_repositories(
    q: Optional[str] = Query(None, description="Search query by name, owner, or full_name"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> RepositoryListResponse:
    """List all registered repositories with search and pagination."""
    query = select(Repository)
    count_query = select(func.count()).select_from(Repository)

    if q:
        search_filter = or_(
            Repository.name.ilike(f"%{q}%"),
            Repository.full_name.ilike(f"%{q}%"),
            Repository.owner.ilike(f"%{q}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Repository.updated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return RepositoryListResponse(
        items=[RepositoryResponse.model_validate(repo) for repo in items],
        total=total,
    )


@router.post("/repositories", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(
    payload: RepositoryCreate,
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """Register or import a repository into the platform."""
    # Check for duplicate
    existing = await db.execute(
        select(Repository).where(Repository.full_name == payload.full_name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository '{payload.full_name}' is already registered.",
        )

    repo = Repository(
        name=payload.name,
        full_name=payload.full_name,
        owner=payload.owner,
        default_branch=payload.default_branch,
        visibility=payload.visibility,
        language=payload.language,
        github_id=payload.github_id,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    return RepositoryResponse.model_validate(repo)


@router.get("/repositories/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """Fetch repository details by ID."""
    result = await db.execute(
        select(Repository).where(Repository.id == repository_id)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return RepositoryResponse.model_validate(repo)


@router.delete("/repositories/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a repository and cascade all associated reviews and findings."""
    result = await db.execute(
        select(Repository).where(Repository.id == repository_id)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    await db.delete(repo)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Repository GitHub Proxy Endpoints
# ---------------------------------------------------------------------------

@router.get("/repositories/{repository_id}/branches", response_model=List[GitHubBranch])
async def get_repository_branches(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
    github_service: BaseGitHubService = Depends(get_github_service),
) -> List[GitHubBranch]:
    """Retrieve branches for a repository directly via GitHub."""
    result = await db.execute(select(Repository).where(Repository.id == repository_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    try:
        return await github_service.list_branches(owner=repo.owner, repo=repo.name)
    except GitHubResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitHubRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.get("/repositories/{repository_id}/commits", response_model=List[GitHubCommit])
async def get_repository_commits(
    repository_id: str,
    branch: Optional[str] = Query(None, description="Branch or commit SHA"),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    github_service: BaseGitHubService = Depends(get_github_service),
) -> List[GitHubCommit]:
    """Retrieve commits for a repository branch via GitHub."""
    result = await db.execute(select(Repository).where(Repository.id == repository_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    target_branch = branch or repo.default_branch
    try:
        return await github_service.list_commits(
            owner=repo.owner, repo=repo.name, branch=target_branch, limit=limit
        )
    except GitHubResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitHubRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.get("/repositories/{repository_id}/tree", response_model=List[GitHubTreeItem])
async def get_repository_tree(
    repository_id: str,
    tree_sha: str = Query("HEAD"),
    recursive: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    github_service: BaseGitHubService = Depends(get_github_service),
) -> List[GitHubTreeItem]:
    """Retrieve file tree for a repository."""
    result = await db.execute(select(Repository).where(Repository.id == repository_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    try:
        return await github_service.get_file_tree(
            owner=repo.owner, repo=repo.name, tree_sha=tree_sha, recursive=recursive
        )
    except GitHubResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitHubRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@router.get("/repositories/{repository_id}/content", response_model=GitHubFileContent)
async def get_repository_content(
    repository_id: str,
    path: str = Query(..., description="File path in repository"),
    ref: Optional[str] = Query(None, description="Branch or commit SHA"),
    db: AsyncSession = Depends(get_db),
    github_service: BaseGitHubService = Depends(get_github_service),
) -> GitHubFileContent:
    """Retrieve file content for a repository file."""
    result = await db.execute(select(Repository).where(Repository.id == repository_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    try:
        return await github_service.get_file_content(
            owner=repo.owner, repo=repo.name, path=path, ref=ref or repo.default_branch
        )
    except GitHubResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitHubRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
