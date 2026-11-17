'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, GitBranch, GitCommit, Printer } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { AgentResultSummary } from '@/components/reviews/agent-result-summary';
import { AgentStatusCard } from '@/components/reviews/agent-status-card';
import { FindingsSummary } from '@/components/reviews/findings-summary';
import { FindingList } from '@/components/reviews/finding-list';
import { RepositorySnapshotCard } from '@/components/reviews/repository-snapshot';
import {
  ApiClientError,
  getReview,
  getReviewAgents,
  getReviewFindings,
  getReviewSnapshot,
} from '@/lib/api';
import type { Review } from '@/types/review';
import type { RepositorySnapshot } from '@/types/analysis';
import type { AgentRun } from '@/types/agent';
import type { Finding } from '@/types/security';

export function ReviewReportView({ reviewId }: { reviewId: string }) {
  const [review, setReview] = useState<Review | null>(null);
  const [agents, setAgents] = useState<AgentRun[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [snapshot, setSnapshot] = useState<RepositorySnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        const [rev, agentRes, findingRes, snap] = await Promise.all([
          getReview(reviewId),
          getReviewAgents(reviewId).catch(() => ({ agents: [] as AgentRun[] })),
          getReviewFindings(reviewId, { limit: 100 }).catch(() => ({ items: [] as Finding[] })),
          getReviewSnapshot(reviewId).catch(() => null),
        ]);
        if (ignore) return;
        setReview(rev);
        setAgents(agentRes.agents);
        setFindings(findingRes.items);
        setSnapshot(snap);
      } catch (err) {
        if (ignore) return;
        if (err instanceof ApiClientError && err.status === 404) setError('Review not found.');
        else if (err instanceof ApiClientError && err.status === 401)
          setError('Your session has expired. Please log in again.');
        else setError(err instanceof ApiClientError ? err.detail : 'Failed to load report.');
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void load();
    return () => {
      ignore = true;
    };
  }, [reviewId]);

  const backLink = (
    <Link href="/dashboard/reports" className="review-detail__back-link">
      <ArrowLeft size={16} />
      Back to Reports
    </Link>
  );

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        {backLink}
        <div className="card h-24 bg-white/5 rounded" />
        <div className="card h-48 bg-white/5 rounded" />
      </div>
    );
  }

  if (error || !review) {
    return (
      <div>
        <PageHeader title="Report Unavailable" description={error ?? 'Report not found.'} />
        {backLink}
      </div>
    );
  }

  const isFinished =
    review.status === 'completed' || review.status === 'completed_with_warnings';

  return (
    <div className="space-y-6">
      {backLink}

      <PageHeader
        title="AI Code Review Report"
        description={`Review ${reviewId.slice(0, 8)}…`}
        actions={
          <>
            <Link
              href={`/dashboard/reviews/${reviewId}`}
              className="btn btn-ghost flex items-center gap-2 text-xs py-2 px-3"
            >
              View Review
            </Link>
            <button
              className="btn btn-ghost flex items-center gap-2 text-xs py-2 px-3"
              onClick={() => window.print()}
            >
              <Printer size={14} />
              Print / Save PDF
            </button>
          </>
        }
      />

      <div className="review-meta-card">
        <div className="review-meta-card__item">
          <GitCommit size={14} className="review-meta-card__icon" />
          <span className="review-meta-card__label">Commit</span>
          <code className="review-meta-card__value review-meta-card__value--mono">
            {review.commit_sha.slice(0, 7)}
          </code>
        </div>
        <div className="review-meta-card__item">
          <GitBranch size={14} className="review-meta-card__icon" />
          <span className="review-meta-card__label">Branch</span>
          <span className="review-meta-card__value">{review.branch}</span>
        </div>
        <div className="review-meta-card__item">
          <span className="review-meta-card__label">Status</span>
          <span className={`review-status-badge review-status-badge--${review.status}`}>
            {review.status.replace(/_/g, ' ')}
          </span>
        </div>
      </div>

      {!isFinished && (
        <div className="p-3.5 rounded-lg border border-amber-500/20 bg-amber-500/10 text-amber-300 text-xs">
          This analysis has not finished yet, so the report may be incomplete.
        </div>
      )}

      <AgentResultSummary review={review} totalFindings={findings.length} snapshot={snapshot} />

      {agents.length > 0 && (
        <section>
          <h4 className="text-[13px] font-semibold text-[var(--text-primary)] mb-3">
            Autonomous Agent Telemetry
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {agents.map((agent) => (
              <AgentStatusCard key={agent.id} agent={agent} />
            ))}
          </div>
        </section>
      )}

      <section className="space-y-4">
        <FindingsSummary findings={findings} />
        <FindingList findings={findings} reviewId={reviewId} />
      </section>

      {snapshot && (
        <section className="pt-4 border-t border-[var(--border-subtle)]">
          <h4 className="text-[13px] font-semibold text-[var(--text-secondary)] mb-3 uppercase tracking-wider">
            Repository Ingestion Snapshot
          </h4>
          <RepositorySnapshotCard snapshot={snapshot} />
        </section>
      )}
    </div>
  );
}
