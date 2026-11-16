'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  GitBranch,
  User,
  Clock,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { RepositorySelector } from '@/components/reviewer/repository-selector';
import { BranchSelector } from '@/components/reviewer/branch-selector';
import { CommitSelector } from '@/components/reviewer/commit-selector';
import { AnalysisOptions } from '@/components/reviewer/analysis-options';
import { AnalyzeButton } from '@/components/reviewer/analyze-button';
import { AnalysisPreview } from '@/components/reviewer/analysis-preview';
import { formatRelativeTime } from '@/lib/utils';
import {
  ApiClientError,
  createReview,
  startAnalysis,
  getGitHubStatus,
  getRepoBranches,
  getRepoCommits,
  getRepositories,
} from '@/lib/api';
import { GitHubConnectModal } from '@/components/github/github-connect-modal';
import type { Repository } from '@/types/repository';
import type { GitHubBranch, GitHubCommit, GitHubStatusResponse } from '@/types/github';
import type { Review } from '@/types/review';

export function ReviewerView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialRepoParam = searchParams.get('repo');

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string>('');
  const [branches, setBranches] = useState<GitHubBranch[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [commits, setCommits] = useState<GitHubCommit[]>([]);
  const [selectedCommitSha, setSelectedCommitSha] = useState<string>('');

  const [loadingRepos, setLoadingRepos] = useState(true);
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [loadingCommits, setLoadingCommits] = useState(false);
  const [submittingReview, setSubmittingReview] = useState(false);

  const [reviewResult, setReviewResult] = useState<Review | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [githubStatus, setGithubStatus] = useState<GitHubStatusResponse | null>(null);
  const [connectModalOpen, setConnectModalOpen] = useState(false);

  // Fetch GitHub status
  useEffect(() => {
    let ignore = false;
    getGitHubStatus()
      .then((status) => {
        if (!ignore) setGithubStatus(status);
      })
      .catch(() => {
        if (!ignore) setGithubStatus({ connected: false });
      });
    return () => {
      ignore = true;
    };
  }, []);

  // 1. Load repositories on mount
  useEffect(() => {
    let ignore = false;

    getRepositories()
      .then((res) => {
        if (ignore) return;
        setRepositories(res.items);
        if (initialRepoParam && res.items.some((r) => r.id === initialRepoParam)) {
          setSelectedRepoId(initialRepoParam);
        } else if (res.items.length > 0) {
          setSelectedRepoId(res.items[0].id);
        }
      })
      .catch((e: unknown) => {
        if (!ignore) {
          setErrorMessage(e instanceof ApiClientError ? e.detail : 'Failed to load repositories');
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoadingRepos(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [initialRepoParam]);

  // 2. Load branches when selectedRepoId changes
  const targetRepoDefaultBranch = repositories.find((r) => r.id === selectedRepoId)?.default_branch;

  useEffect(() => {
    if (!selectedRepoId) return;

    let ignore = false;

    getRepoBranches(selectedRepoId)
      .then((branchList) => {
        if (ignore) return;
        setBranches(branchList);

        if (branchList.length > 0) {
          const defaultBranchMatch = branchList.find(
            (b) => b.name === targetRepoDefaultBranch,
          );
          const chosen = defaultBranchMatch ? defaultBranchMatch.name : branchList[0].name;
          setSelectedBranch(chosen);
        } else {
          setSelectedBranch('');
        }
      })
      .catch((e: unknown) => {
        if (!ignore) {
          setErrorMessage(e instanceof ApiClientError ? e.detail : 'Could not retrieve branches from GitHub');
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoadingBranches(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [selectedRepoId, targetRepoDefaultBranch]);

  // 3. Load commits when selectedBranch changes
  useEffect(() => {
    if (!selectedRepoId || !selectedBranch) return;

    let ignore = false;

    getRepoCommits(selectedRepoId, selectedBranch, 20)
      .then((commitList) => {
        if (ignore) return;
        setCommits(commitList);

        if (commitList.length > 0) {
          setSelectedCommitSha(commitList[0].sha);
        } else {
          setSelectedCommitSha('');
        }
      })
      .catch((e: unknown) => {
        if (!ignore) {
          setErrorMessage(e instanceof ApiClientError ? e.detail : 'Could not retrieve commits for branch');
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoadingCommits(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [selectedRepoId, selectedBranch]);

  function handleSelectRepo(repoId: string) {
    setSelectedRepoId(repoId);
    setBranches([]);
    setSelectedBranch('');
    setCommits([]);
    setSelectedCommitSha('');
    setLoadingBranches(true);
  }

  function handleSelectBranch(branch: string) {
    setSelectedBranch(branch);
    setCommits([]);
    setSelectedCommitSha('');
    setLoadingCommits(true);
  }

  // Current selected entities
  const currentRepo = repositories.find((r) => r.id === selectedRepoId);
  const currentCommit = commits.find((c) => c.sha === selectedCommitSha);

  const canAnalyze = Boolean(
    selectedRepoId && selectedBranch && selectedCommitSha && !submittingReview,
  );

  async function handleStartReview() {
    if (!canAnalyze) return;
    setSubmittingReview(true);
    setErrorMessage(null);
    setReviewResult(null);

    try {
      const rev = await createReview({
        repository_id: selectedRepoId,
        commit_sha: selectedCommitSha,
        branch: selectedBranch,
      });

      if (!rev?.id) {
        throw new Error('Review was created but no valid review ID was returned from server.');
      }

      // Automatically trigger unified analysis pipeline
      try {
        await startAnalysis(rev.id);
      } catch (analyzeErr) {
        console.warn('Initial analysis initiation:', analyzeErr);
      }

      // Navigate to the review detail page with validated review ID
      router.push(`/dashboard/reviews/${rev.id}`);
    } catch (e: unknown) {
      setErrorMessage(
        e instanceof ApiClientError
          ? e.detail
          : e instanceof Error
          ? e.message
          : 'Failed to schedule code review',
      );
    } finally {
      setSubmittingReview(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="New Code Review"
        description="Select a repository, branch, and commit to configure the security and quality analysis."
      />

      {/* Disconnected GitHub Prompt */}
      {githubStatus && !githubStatus.connected && (
        <div
          className="p-4 rounded-xl mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
          style={{
            background: 'rgba(99, 102, 241, 0.08)',
            border: '1px solid var(--primary-border)',
          }}
        >
          <div>
            <h3 className="text-xs font-semibold text-white">GitHub connection required</h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Connect your GitHub account to access branches and commits for analysis.
            </p>
          </div>
          <button
            onClick={() => setConnectModalOpen(true)}
            className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-white flex-shrink-0 shadow-sm transition-all hover:brightness-110"
            style={{ background: 'var(--primary)' }}
          >
            Connect GitHub
          </button>
        </div>
      )}

      {/* Review Scheduled Banner */}
      {reviewResult && (
        <div
          className="p-4 rounded-lg mb-6 flex items-start justify-between gap-3"
          style={{
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
          }}
        >
          <div className="flex items-start gap-3">
            <CheckCircle size={18} style={{ color: 'var(--success)' }} className="mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
                Review Successfully Queued
              </h3>
              <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                Review for commit <span className="mono font-medium">{reviewResult.commit_sha.slice(0, 7)}</span> on branch <span className="mono">{reviewResult.branch}</span> has been queued. The automated multi-agent analysis engine will evaluate this review in Phase 5.
              </p>
            </div>
          </div>
          <Link
            href="/dashboard/reviews"
            className="px-3 py-1.5 rounded text-[12px] font-medium transition-colors flex-shrink-0"
            style={{ background: 'var(--primary)', color: 'white' }}
          >
            View Reviews
          </Link>
        </div>
      )}

      {/* Error Alert */}
      {errorMessage && (
        <div
          className="p-3 rounded-lg mb-6 flex items-center gap-2 text-[12px]"
          style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            color: '#ef4444',
          }}
        >
          <AlertCircle size={15} className="flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column — configuration */}
        <div className="lg:col-span-2 space-y-5">
          {/* Target selection card */}
          <div className="card space-y-4">
            <h2 className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
              Analysis Target
            </h2>

            <RepositorySelector
              repositories={repositories}
              selectedId={selectedRepoId}
              onSelect={handleSelectRepo}
              loading={loadingRepos}
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <BranchSelector
                branches={branches}
                selectedBranch={selectedBranch}
                onSelect={handleSelectBranch}
                disabled={!selectedRepoId}
                loading={loadingBranches}
              />
              <CommitSelector
                commits={commits}
                selectedSha={selectedCommitSha}
                onSelect={setSelectedCommitSha}
                disabled={!selectedBranch}
                loading={loadingCommits}
              />
            </div>

            {/* Selected Commit Metadata */}
            {currentCommit && currentRepo && (
              <div
                className="p-3 rounded-lg mt-3 space-y-2 text-[12px]"
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Selected Commit
                  </span>
                  <span className="mono text-[11px]" style={{ color: 'var(--primary-hover)' }}>
                    {currentCommit.short_sha}
                  </span>
                </div>
                <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                  {currentCommit.message || 'No commit message'}
                </p>
                <div className="flex items-center gap-4 flex-wrap text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                  <span className="flex items-center gap-1">
                    <User size={11} />
                    {currentCommit.author_name}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock size={11} />
                    {formatRelativeTime(currentCommit.date)}
                  </span>
                  <span className="flex items-center gap-1 mono">
                    <GitBranch size={11} />
                    {selectedBranch}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Analysis options toggles */}
          <AnalysisOptions disabled={!selectedRepoId} />

          {/* Review action CTA */}
          <AnalyzeButton
            disabled={!canAnalyze}
            loading={submittingReview}
            reason={
              repositories.length === 0
                ? 'Connect a repository first'
                : !selectedRepoId
                ? 'Select a repository'
                : !selectedBranch
                ? 'Select a branch'
                : !selectedCommitSha
                ? 'Select a commit'
                : undefined
            }
            onClick={handleStartReview}
          />
        </div>

        {/* Right column — pipeline preview */}
        <div>
          <AnalysisPreview repositoryConnected={Boolean(selectedRepoId)} />
        </div>
      </div>

      <GitHubConnectModal
        isOpen={connectModalOpen}
        onClose={() => setConnectModalOpen(false)}
      />
    </div>
  );
}
