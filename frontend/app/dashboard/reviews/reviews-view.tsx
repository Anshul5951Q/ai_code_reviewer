'use client';

import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/layout/page-header';
import { ReviewTable } from '@/components/reviews/review-table';
import { ReviewFiltersBar } from '@/components/reviews/review-filters';
import { LoadingState } from '@/components/common/loading-state';
import { ApiClientError, getReviews } from '@/lib/api';
import type { Review, ReviewFilters } from '@/types/review';

const DEFAULT_FILTERS: ReviewFilters = {
  search: '',
  repository: '',
  status: 'all',
  severity: '',
  dateFrom: '',
  dateTo: '',
};

export function ReviewsView() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<ReviewFilters>(DEFAULT_FILTERS);

  useEffect(() => {
    let ignore = false;

    getReviews({
      status: filters.status !== 'all' ? filters.status : undefined,
    })
      .then((res) => {
        if (!ignore) {
          setReviews(res.items);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (!ignore) {
          setError(e instanceof ApiClientError ? e.detail : 'Failed to load reviews');
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [filters.status]);

  function handleFilterChange(newFilters: ReviewFilters) {
    setLoading(true);
    setFilters(newFilters);
  }

  const filtered = reviews.filter((r) => {
    if (
      filters.search &&
      !r.repository_id.toLowerCase().includes(filters.search.toLowerCase()) &&
      !r.branch.toLowerCase().includes(filters.search.toLowerCase()) &&
      !r.commit_sha.toLowerCase().includes(filters.search.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  return (
    <div>
      <PageHeader
        title="Reviews"
        description="All code review analysis runs across your repositories."
      />

      <ReviewFiltersBar filters={filters} onChange={handleFilterChange} />

      {loading ? (
        <LoadingState message="Loading review history..." />
      ) : error ? (
        <div
          className="p-6 rounded-lg text-center my-6 text-[13px]"
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', color: 'var(--text-secondary)' }}
        >
          {error}
        </div>
      ) : (
        <ReviewTable reviews={filtered} />
      )}
    </div>
  );
}
