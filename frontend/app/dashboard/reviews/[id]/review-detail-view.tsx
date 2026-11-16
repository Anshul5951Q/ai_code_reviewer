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
  const isValidReviewId = Boolean(
    reviewId && typeof reviewId === 'string' && reviewId.trim() !== '' && reviewId !== 'undefined'
  );

  const [review, setReview] = useState<Review | null>(null);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [snapshot, setSnapshot] = useState<RepositorySnapshot | null>(null);
  const [agents, setAgents] = useState<AgentRun[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);

  const [loading, setLoading] = useState<boolean>(() => isValidReviewId);
  const [error, setError] = useState<string | null>(() =>
    isValidReviewId ? null : 'Invalid or missing review ID.'
  );
  const [startingAnalysis, setStartingAnalysis] = useState(false);

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMounted = useRef(true);
  const hasFetchedSnapshot = useRef(false);
  const hasFetchedTerminalFindings = useRef(false);

  // Fetch review details
  const fetchReview = useCallback(async () => {
    if (!isValidReviewId) return null;
    try {
      const rev = await getReview(reviewId);
      if (!isMounted.current) return null;
      setReview(rev);
      return rev;
    } catch (err) {
      if (!isMounted.current) return null;
      if (err instanceof ApiClientError && err.status === 401) {
        setError('Your session has expired. Please log in again.');
        return null;
      }
      if (err instanceof ApiClientError && err.status === 404) {
        setError('Review Not Found');
        return null;
      }
      const msg = err instanceof ApiClientError ? err.detail : 'Failed to load review.';
      setError(msg);
      return null;
    }
  }, [reviewId, isValidReviewId]);

  // Fetch current ingestion job status
  const fetchJob = useCallback(async (): Promise<AnalysisJob | null> => {
    if (!isValidReviewId) return null;
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
  }, [reviewId, isValidReviewId]);

  // Fetch completed snapshot
  const fetchSnapshot = useCallback(async () => {
    if (!isValidReviewId) return;
    try {
      const snap = await getReviewSnapshot(reviewId);
      if (!isMounted.current) return;
      setSnapshot(snap);
    } catch {
      // Not available yet
    }
  }, [reviewId, isValidReviewId]);

  // Fetch agent runs
  const fetchAgents = useCallback(async () => {
    if (!isValidReviewId) return [];
    try {
      const res = await getReviewAgents(reviewId);
      if (!isMounted.current) return [];
      setAgents(res.agents);
      return res.agents;
    } catch {
      return [];
    }
  }, [reviewId, isValidReviewId]);

  // Fetch findings
  const fetchFindings = useCallback(async () => {
    if (!isValidReviewId) return [];
    try {
      const res = await getReviewFindings(reviewId, { limit: 100 });
      if (!isMounted.current) return [];
      setFindings(res.items);
      return res.items;
    } catch {
      return [];
    }
  }, [reviewId, isValidReviewId]);

  const pollCallbackRef = useRef<() => void>(() => {});

  // Optimized Polling loop with parallel queries and Page Visibility check
  const checkStatusAndSchedulePoll = useCallback(async () => {
    if (!isMounted.current || !isValidReviewId) return;

    // Do not poll if the browser tab is hidden
    if (typeof document !== 'undefined' && document.hidden) {
      return;
    }

    // Parallelize active status queries across the network
    const [currentRev, currentJob, currentAgents] = await Promise.all([
      fetchReview(),
      fetchJob(),
      fetchAgents(),
    ]);

    // Fetch snapshot only once upon ingestion completion
    if (currentJob?.status === 'completed' && !hasFetchedSnapshot.current) {
      hasFetchedSnapshot.current = true;
      void fetchSnapshot();
    }

    // Check if either pipeline or multi-agent review is running
    const isJobRunning =
      currentJob && !['completed', 'failed', 'cancelled'].includes(currentJob.status);
    const isReviewRunning =
      currentRev?.status === 'running' ||
      currentRev?.status === 'ingesting';
    const isAgentsRunning =
      currentAgents.some((a) => a.status === 'running' || a.status === 'queued' || a.status === 'analyzing');

    const isRunning = isJobRunning || isReviewRunning || isAgentsRunning;

    // Refresh findings initially and upon terminal completion
    if (!isRunning || !hasFetchedTerminalFindings.current) {
      void fetchFindings();
      if (!isRunning && currentRev?.status === 'completed') {
        hasFetchedTerminalFindings.current = true;
      }
    }

    if (isRunning) {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
      pollTimerRef.current = setTimeout(() => {
        pollCallbackRef.current();
      }, POLL_INTERVAL_MS);
    }
  }, [fetchReview, fetchJob, fetchSnapshot, fetchAgents, fetchFindings, isValidReviewId]);

  useEffect(() => {
    pollCallbackRef.current = () => {
      void checkStatusAndSchedulePoll();
    };
  }, [checkStatusAndSchedulePoll]);

  // Page visibility listener: resume immediately when user returns to tab
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (typeof document !== 'undefined' && !document.hidden && isMounted.current) {
        void checkStatusAndSchedulePoll();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [checkStatusAndSchedulePoll]);

  // Initial load
  useEffect(() => {
    isMounted.current = true;

    if (!isValidReviewId) return;

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
  }, [checkStatusAndSchedulePoll, isValidReviewId]);

  // Unified single workflow: start full end-to-end analysis pipeline
  const handleStartAnalysis = async () => {
    if (!isValidReviewId) return;
    setStartingAnalysis(true);
    try {
      await startAnalysis(reviewId);
      void checkStatusAndSchedulePoll();
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.detail : 'Failed to start analysis.';
      setError(msg);
    } finally {
      setStartingAnalysis(false);
    }
  };

  if (loading) {
    return (
      <div className="review-detail space-y-6 animate-pulse">
        <div className="review-detail__header">
          <Link href="/dashboard/reviews" className="review-detail__back-link">
            <ArrowLeft size={16} />
            Back to Reviews
          </Link>
          <PageHeader
            title="Multi-Agent Code Intelligence"
            description={`Loading review ${isValidReviewId ? reviewId.slice(0, 8) : ''}…`}
          />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card h-24 bg-white/5 rounded" />
          ))}
        </div>
        <div className="card h-48 bg-white/5 rounded" />
      </div>
    );
  }

  if (error && !review) {
    const isAuthError =
      error.toLowerCase().includes('session') ||
      error.toLowerCase().includes('log in') ||
      error.toLowerCase().includes('expired');
    return (
      <div className="review-detail-error">
        <PageHeader
          title={isAuthError ? 'Authentication Required' : 'Review Not Found'}
          description={error}
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

  const isPipelineActive =
    startingAnalysis ||
    (job && !['completed', 'failed', 'cancelled'].includes(job.status)) ||
    review?.status === 'running' ||
    review?.status === 'ingesting' ||
    agents.some((a) => a.status === 'running' || a.status === 'queued' || a.status === 'analyzing');

  const isPipelineFailed = (job?.status === 'failed' || review?.status === 'failed') && !isPipelineActive;
  const hasCompletedAgents =
    review?.status === 'completed' ||
    review?.status === 'completed_with_warnings' ||
    agents.some((a) => a.status === 'completed');
  const hasNoIngestion = !job && !snapshot && !hasCompletedAgents;

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
            !isPipelineActive && (
              <button
                className="btn btn-primary flex items-center gap-2 text-xs py-2 px-3"
                onClick={() => void handleStartAnalysis()}
                disabled={startingAnalysis}
              >
                {startingAnalysis ? (
                  <>
                    <RefreshCw size={14} className="spin" />
                    Starting Analysis…
                  </>
                ) : (
                  <>
                    <Sparkles size={14} />
                    {hasCompletedAgents ? 'Re-run Full Analysis' : 'Start Full Analysis'}
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

      {/* Warning banner for partially completed analysis */}
      {review?.status === 'completed_with_warnings' && (
        <div className="p-3.5 rounded-lg border border-amber-500/20 bg-amber-500/10 text-amber-300 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-amber-400 font-semibold">Partial Analysis Notice:</span>
            <span>
              One or more non-fatal agent evaluations encountered errors. Valid findings from successful agents have been preserved.
              {agents.filter((a) => a.status === 'failed').length > 0 && (
                <span className="ml-1 text-amber-200">
                  (Failed: {agents.filter((a) => a.status === 'failed').map((a) => a.agent_type.replace(/_/g, ' ')).join(', ')})
                </span>
              )}
            </span>
          </div>
        </div>
      )}

      {/* Single Analysis Start Card if repository has not been analyzed yet */}
      {hasNoIngestion && !isPipelineActive && !error && (
        <div className="review-detail__start">
          <div className="review-start-card">
            <div className="review-start-card__icon">⚡</div>
            <h3 className="review-start-card__title">Autonomous Code Review</h3>
            <p className="review-start-card__desc">
              Execute full end-to-end repository ingestion, multi-agent code understanding, code quality, and security vulnerability analysis in a single workflow.
            </p>
            <button
              className="btn btn-primary review-start-card__btn"
              onClick={() => void handleStartAnalysis()}
              disabled={startingAnalysis}
            >
              {startingAnalysis ? (
                <>
                  <RefreshCw size={16} className="spin" />
                  Starting Analysis…
                </>
              ) : (
                <>⚡ Start Full Analysis</>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Analysis progress (Live Pipeline Progress) */}
      {isPipelineActive && job && (
        <ReviewAnalysisProgress job={job} />
      )}

      {/* Pipeline Error state */}
      {isPipelineFailed && job && (
        <AnalysisErrorCard
          error={job.error ?? 'An error occurred during repository analysis.'}
          onRetry={() => void handleStartAnalysis()}
        />
      )}

      {/* Multi-Agent Pipeline Telemetry */}
      {(isPipelineActive || hasCompletedAgents) && (
        <AgentAnalysisProgress
          agents={agents}
          isAnalysisRunning={isPipelineActive}
          onTriggerAnalysis={() => void handleStartAnalysis()}
          canTriggerAnalysis={!isPipelineActive}
        />
      )}

      {/* Agent Results Summary (Scores) */}
      {review && hasCompletedAgents && (
        <AgentResultSummary review={review} totalFindings={findings.length} snapshot={snapshot} />
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
          <FindingList findings={findings} reviewId={reviewId} />
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
