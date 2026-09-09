from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.review import Review
from app.schemas.finding import FindingListResponse, FindingResponse
from app.schemas.review import (
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
)

router = APIRouter(tags=["reviews"])


@router.get("/reviews", response_model=ReviewListResponse)
async def list_reviews(
    repository_id: Optional[str] = Query(None, description="Filter reviews by repository ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (queued, running, completed, failed, cancelled)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ReviewListResponse:
    """Return reviews with optional filtering and pagination."""
    query = select(Review)
    count_query = select(func.count()).select_from(Review)

    if repository_id:
        query = query.where(Review.repository_id == repository_id)
        count_query = count_query.where(Review.repository_id == repository_id)
    if status_filter:
        query = query.where(Review.status == status_filter)
        count_query = count_query.where(Review.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Review.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return ReviewListResponse(
        items=[ReviewResponse.model_validate(r) for r in items],
        total=total,
    )


@router.post("/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    payload: ReviewCreate,
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Schedule / queue a new code review for analysis."""
    # Verify repository exists
    repo_res = await db.execute(
        select(Repository).where(Repository.id == payload.repository_id)
    )
    if repo_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{payload.repository_id}' not found.",
        )

    review = Review(
        repository_id=payload.repository_id,
        commit_sha=payload.commit_sha,
        branch=payload.branch,
        status="queued",
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    return ReviewResponse.model_validate(review)


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Return a single review by ID."""
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )
    return ReviewResponse.model_validate(review)


@router.get("/reviews/{review_id}/findings", response_model=FindingListResponse)
async def get_review_findings(
    review_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity (critical, high, medium, low, info)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by finding status"),
    agent_type: Optional[str] = Query(None, description="Filter by source or agent type"),
    file_path: Optional[str] = Query(None, description="Filter by file path match"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FindingListResponse:
    """Return findings detected in a review."""
    rev_check = await db.execute(select(Review).where(Review.id == review_id))
    if rev_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    query = select(Finding).where(Finding.review_id == review_id)
    count_query = select(func.count()).select_from(Finding).where(Finding.review_id == review_id)

    if severity:
        query = query.where(Finding.severity == severity.lower())
        count_query = count_query.where(Finding.severity == severity.lower())
    if category:
        query = query.where(Finding.category == category.lower())
        count_query = count_query.where(Finding.category == category.lower())
    if status_filter:
        query = query.where(Finding.status == status_filter.lower())
        count_query = count_query.where(Finding.status == status_filter.lower())
    if agent_type:
        query = query.where(Finding.source == agent_type)
        count_query = count_query.where(Finding.source == agent_type)
    if file_path:
        query = query.where(Finding.file_path.like(f"%{file_path}%"))
        count_query = count_query.where(Finding.file_path.like(f"%{file_path}%"))

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    query = query.order_by(Finding.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return FindingListResponse(
        items=[FindingResponse.model_validate(f) for f in items],
        total=total,
    )
