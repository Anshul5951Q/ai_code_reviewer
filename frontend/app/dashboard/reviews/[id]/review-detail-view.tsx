'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  RefreshCw,
  GitCommit,
  GitBranch,
  Clock,
  Sparkles,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { LoadingState } from '@/components/common/loading-state';
import { ReviewAnalysisProgress } from '@/components/reviews/review-analysis-progress';
import { RepositorySnapshotCard } from '@/components/reviews/repository-snapshot';
import { AnalysisErrorCard } from '@/components/reviews/analysis-error';
import { AgentAnalysisProgress } from '@/components/reviews/agent-analysis-progress';
import { AgentStatusCard } from '@/components/reviews/agent-status-card';
import { AgentResultSummary } from '@/components/reviews/agent-result-summary';
import { FindingsSummary } from '@/components/reviews/findings-summary';
import { FindingList } from '@/components/reviews/finding-list';
import {
  ApiClientError,
  getReview,
  getAnalysisStatus,
  getReviewSnapshot,
  startAnalysis,
  runReviewAnalysis,
  getReviewAgents,
  getReviewFindings,
} from '@/lib/api';
import type { Review } from '@/types/review';
import type { AnalysisJob, RepositorySnapshot } from '@/types/analysis';
import type { AgentRun } from '@/types/agent';
import type { Finding } from '@/types/security';

// Polling interval in ms when analysis is active
const POLL_INTERVAL_MS = 2500;

interface ReviewDetailViewProps {
  reviewId: string;
}

export function ReviewDetailView({ reviewId }: ReviewDetailViewProps) {
  const [review, setReview] = useState<Review | null>(null);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [snapshot, setSnapshot] = useState<RepositorySnapshot | null>(null);
  const [agents, setAgents] = useState<AgentRun[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingIngestion, setStartingIngestion] = useState(false);
  const [startingAgentRun, setStartingAgentRun] = useState(false);

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMounted = useRef(true);

  // Fetch review details
  const fetchReview = useCallback(async () => {
    try {
      const rev = await getReview(reviewId);
      if (!isMounted.current) return null;
      setReview(rev);
      return rev;
    } catch (err) {
      if (!isMounted.current) return null;
      const msg = err instanceof ApiClientError ? err.detail : 'Failed to load review.';
      setError(msg);
      return null;
    }
  }, [reviewId]);

  // Fetch current ingestion job status
  const fetchJob = useCallback(async (): Promise<AnalysisJob | null> => {
    try {
      const j = await getAnalysisStatus(reviewId);
      if (!isMounted.current) return null;
      setJob(j);
      return j;
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 404) {
        return null;
      }
      return null;
    }
  }, [reviewId]);

  // Fetch completed snapshot
  const fetchSnapshot = useCallback(async () => {
    try {
      const snap = await getReviewSnapshot(reviewId);
      if (!isMounted.current) return;
      setSnapshot(snap);
    } catch {
      // Not available yet
    }
  }, [reviewId]);

  // Fetch agent runs
  const fetchAgents = useCallback(async () => {
    try {
      const res = await getReviewAgents(reviewId);
      if (!isMounted.current) return [];
      setAgents(res.agents);
      return res.agents;
    } catch {
      return [];
    }
  }, [reviewId]);

  // Fetch findings
  const fetchFindings = useCallback(async () => {
    try {
      const res = await getReviewFindings(reviewId, { limit: 100 });
      if (!isMounted.current) return [];
      setFindings(res.items);
      return res.items;
    } catch {
      return [];
    }
  }, [reviewId]);

  const pollCallbackRef = useRef<() => void>(() => {});

  // Polling loop
  const checkStatusAndSchedulePoll = useCallback(async () => {
    if (!isMounted.current) return;

    const currentRev = await fetchReview();
    const currentJob = await fetchJob();

    if (currentJob?.status === 'completed') {
      await fetchSnapshot();
    }

    const currentAgents = await fetchAgents();
    await fetchFindings();

    // Check if either ingestion is running or multi-agent review is running
    const isIngestionRunning =
      currentJob && !['completed', 'failed', 'cancelled'].includes(currentJob.status);
    const isAgentsRunning =
      currentRev?.status === 'running' ||
      currentAgents.some((a) => a.status === 'running' || a.status === 'queued');

    if (isIngestionRunning || isAgentsRunning) {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
      pollTimerRef.current = setTimeout(() => {
        pollCallbackRef.current();
      }, POLL_INTERVAL_MS);
    }
  }, [fetchReview, fetchJob, fetchSnapshot, fetchAgents, fetchFindings]);

  useEffect(() => {
    pollCallbackRef.current = () => {
      void checkStatusAndSchedulePoll();
    };
  }, [checkStatusAndSchedulePoll]);

  // Initial load
  useEffect(() => {
    isMounted.current = true;

    const init = async () => {
      setLoading(true);
      await checkStatusAndSchedulePoll();
      if (isMounted.current) setLoading(false);
    };

    void init();

    return () => {
      isMounted.current = false;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [checkStatusAndSchedulePoll]);

  // Start Phase 3 ingestion
  const handleStartIngestion = async () => {
    setStartingIngestion(true);
    try {
      await startAnalysis(reviewId);
      void checkStatusAndSchedulePoll();
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.detail : 'Failed to start ingestion.';
      setError(msg);
    } finally {
      setStartingIngestion(false);
    }
  };

  // Start Phase 5 multi-agent review
  const handleStartAgentRun = async () => {
    setStartingAgentRun(true);
    try {
      await runReviewAnalysis(reviewId);
      void checkStatusAndSchedulePoll();
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.detail : 'Failed to start multi-agent analysis.';
      setError(msg);
    } finally {
      setStartingAgentRun(false);
    }
  };

  if (loading) {
    return <LoadingState message="Loading review details..." />;
  }

  if (error && !review) {
    return (
      <div className="review-detail-error">
        <PageHeader
          title="Review Not Found"
          description="The requested review could not be loaded."
        />
        <div className="review-detail-error__back">
          <Link href="/dashboard/reviews" className="btn btn-ghost">
            <ArrowLeft size={16} />
            Back to Reviews
          </Link>
        </div>
      </div>
    );
  }

  const isIngestionActive = job && !['completed', 'failed', 'cancelled'].includes(job.status);
  const isIngestionFailed = job?.status === 'failed';
  const isIngestionCompleted = job?.status === 'completed' || !!snapshot;
  const hasNoIngestion = !job && !snapshot;

  const isAgentsRunning =
    review?.status === 'running' ||
    agents.some((a) => a.status === 'running' || a.status === 'queued');
  const hasCompletedAgents =
    review?.status === 'completed' ||
    review?.status === 'completed_with_warnings' ||
    agents.some((a) => a.status === 'completed');

  return (
    <div className="review-detail space-y-6">
      <div className="review-detail__header">
        <Link href="/dashboard/reviews" className="review-detail__back-link">
          <ArrowLeft size={16} />
          Back to Reviews
        </Link>

        <PageHeader
          title="Multi-Agent Code Intelligence"
          description={`Review ${reviewId.slice(0, 8)}…`}
          actions={
            isIngestionCompleted &&
            !isAgentsRunning && (
              <button
                className="btn btn-primary flex items-center gap-2 text-xs py-2 px-3"
                onClick={() => void handleStartAgentRun()}
                disabled={startingAgentRun}
              >
                {startingAgentRun ? (
                  <>
                    <RefreshCw size={14} className="spin" />
                    Starting Agents…
                  </>
                ) : (
                  <>
                    <Sparkles size={14} />
                    {hasCompletedAgents ? 'Re-run Multi-Agent Analysis' : 'Run Multi-Agent Review'}
                  </>
                )}
              </button>
            )
          }
        />
      </div>

      {/* Review metadata */}
      {review && (
        <div className="review-detail__meta">
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
              <Clock size={14} className="review-meta-card__icon" />
              <span className="review-meta-card__label">Status</span>
              <span className={`review-status-badge review-status-badge--${review.status}`}>
                {review.status.replace(/_/g, ' ')}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Ingestion Start Card if repository has not been ingested yet */}
      {hasNoIngestion && !error && (
        <div className="review-detail__start">
          <div className="review-start-card">
            <div className="review-start-card__icon">⚡</div>
            <h3 className="review-start-card__title">Repository Ingestion Required</h3>
            <p className="review-start-card__desc">
              Before AI agents can analyze the codebase, ingest and snapshot the repository at this commit.
            </p>
            <button
              className="btn btn-primary review-start-card__btn"
              onClick={() => void handleStartIngestion()}
              disabled={startingIngestion}
            >
              {startingIngestion ? (
                <>
                  <RefreshCw size={16} className="spin" />
                  Starting Ingestion…
                </>
              ) : (
                <>⚡ Start Ingestion</>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Ingestion progress (Phase 3) */}
      {(isIngestionActive || job) && !isIngestionCompleted && !isIngestionFailed && job && (
        <ReviewAnalysisProgress job={job} />
      )}

      {/* Ingestion Error state */}
      {isIngestionFailed && job && (
        <AnalysisErrorCard
          error={job.error ?? 'An unknown error occurred during repository ingestion.'}
          onRetry={() => void handleStartIngestion()}
        />
      )}

      {/* Phase 5 Multi-Agent Pipeline Progress */}
      {isIngestionCompleted && (
        <AgentAnalysisProgress
          agents={agents}
          isAnalysisRunning={isAgentsRunning}
          onTriggerAnalysis={() => void handleStartAgentRun()}
          canTriggerAnalysis={!isAgentsRunning}
        />
      )}

      {/* Agent Results Summary (Scores) */}
      {review && hasCompletedAgents && (
        <AgentResultSummary review={review} totalFindings={findings.length} />
      )}

      {/* Agent Status Cards Grid */}
      {agents.length > 0 && (
        <div>
          <h4 className="text-[13px] font-semibold text-[var(--text-primary)] mb-3">
            Autonomous Agent Telemetry
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {agents.map((agent) => (
              <AgentStatusCard key={agent.id} agent={agent} />
            ))}
          </div>
        </div>
      )}

      {/* Findings Breakdown & List */}
      {hasCompletedAgents && (
        <div className="space-y-4">
          <FindingsSummary findings={findings} />
          <FindingList findings={findings} />
        </div>
      )}

      {/* Repository Snapshot (Phase 3) */}
      {snapshot && (
        <div className="pt-4 border-t border-[var(--border-subtle)]">
          <h4 className="text-[13px] font-semibold text-[var(--text-secondary)] mb-3 uppercase tracking-wider">
            Repository Ingestion Snapshot
          </h4>
          <RepositorySnapshotCard snapshot={snapshot} />
        </div>
      )}
    </div>
  );
}
