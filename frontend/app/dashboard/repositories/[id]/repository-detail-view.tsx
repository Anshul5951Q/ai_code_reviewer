'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  ExternalLink,
  GitBranch,
  GitCommit,
  Globe,
  Lock,
  ScanSearch,
  AlertCircle,
  Loader2,
  Clock,
  Code2,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { LabelBadge, StatusBadge } from '@/components/common/status-badge';
import { LoadingState } from '@/components/common/loading-state';
import { formatRelativeTime, formatScore } from '@/lib/utils';
import {
  ApiClientError,
  getRepoBranches,
  getRepoCommits,
  getRepository,
  getReviews,
} from '@/lib/api';
import type { Repository } from '@/types/repository';
import type { Review } from '@/types/review';
import type { GitHubBranch, GitHubCommit } from '@/types/github';

interface Props {
  repositoryId: string;
}

export function RepositoryDetailView({ repositoryId }: Props) {
  const [repository, setRepository] = useState<Repository | null>(null);
  const [branches, setBranches] = useState<GitHubBranch[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [commits, setCommits] = useState<GitHubCommit[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingCommits, setLoadingCommits] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadData() {
      try {
        const repo = await getRepository(repositoryId);
        if (!active) return;
        setRepository(repo);
        setSelectedBranch(repo.default_branch);

        // Load reviews
        try {
          const revRes = await getReviews({ repository_id: repo.id });
          if (active) setReviews(revRes.items);
        } catch {
          if (active) setReviews([]);
        }

        // Load branches
        try {
          const bList = await getRepoBranches(repo.id);
          if (active) setBranches(bList);
        } catch {
          if (active) setBranches([]);
        }
      } catch (e: unknown) {
        if (active) {
          const msg = e instanceof ApiClientError ? e.detail : 'Failed to load repository details';
          setError(msg);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    loadData();
    return () => {
      active = false;
    };
  }, [repositoryId]);

  // Load commits when selectedBranch changes
  useEffect(() => {
    if (!repository || !selectedBranch) return;
    let active = true;

    async function loadCommitsForBranch() {
      setLoadingCommits(true);
      try {
        const cList = await getRepoCommits(repositoryId, selectedBranch, 15);
        if (active) setCommits(cList);
      } catch {
        if (active) setCommits([]);
      } finally {
        if (active) setLoadingCommits(false);
      }
    }

    loadCommitsForBranch();
    return () => {
      active = false;
    };
  }, [repository, repositoryId, selectedBranch]);

  if (loading) {
    return <LoadingState message="Loading repository details..." />;
  }

  if (error || !repository) {
    return (
      <div
        className="p-8 rounded-lg text-center my-6 flex flex-col items-center justify-center gap-3"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)' }}
      >
        <AlertCircle size={28} style={{ color: 'var(--critical)' }} />
        <h2 className="text-[14px] font-semibold" style={{ color: 'var(--text-primary)' }}>
          Repository Not Found
        </h2>
        <p className="text-[12px] max-w-md" style={{ color: 'var(--text-secondary)' }}>
          {error ?? 'Could not find the requested repository.'}
        </p>
        <Link
          href="/dashboard/repositories"
          className="mt-2 flex items-center gap-1.5 px-3 py-1.5 rounded text-[12px] font-medium"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-default)', color: 'var(--text-primary)' }}
        >
          <ArrowLeft size={13} />
          Back to Repositories
        </Link>
      </div>
    );
  }

  const isPrivate = repository.visibility === 'private';

  return (
    <div className="space-y-6">
      {/* Back button */}
      <div>
        <Link
          href="/dashboard/repositories"
          className="inline-flex items-center gap-1.5 text-[12px] transition-colors hover:underline"
          style={{ color: 'var(--text-secondary)' }}
        >
          <ArrowLeft size={13} />
          Back to Repositories
        </Link>
      </div>

      {/* Header */}
      <PageHeader
        title={repository.name}
        description={repository.full_name}
        actions={
          <div className="flex items-center gap-2">
            <Link
              href={`/dashboard/reviewer?repo=${repository.id}`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[13px] font-medium transition-colors"
              style={{ background: 'var(--primary)', color: 'white' }}
            >
              <ScanSearch size={13} />
              Launch Review
            </Link>
            <a
              href={`https://github.com/${repository.full_name}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[13px] font-medium transition-colors hover:bg-white/5"
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                color: 'var(--text-secondary)',
              }}
            >
              <ExternalLink size={13} />
              GitHub
            </a>
          </div>
        }
      />

      {/* Metadata bar */}
      <div
        className="card flex flex-wrap items-center gap-6 text-[12px]"
        style={{ borderColor: 'var(--border-subtle)' }}
      >
        <div className="flex items-center gap-1.5">
          {isPrivate ? <Lock size={13} /> : <Globe size={13} />}
          <span style={{ color: 'var(--text-secondary)' }}>Visibility:</span>
          <LabelBadge label={repository.visibility} variant="outline" />
        </div>

        {repository.language && (
          <div className="flex items-center gap-1.5">
            <Code2 size={13} style={{ color: 'var(--text-tertiary)' }} />
            <span style={{ color: 'var(--text-secondary)' }}>Language:</span>
            <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
              {repository.language}
            </span>
          </div>
        )}

        <div className="flex items-center gap-1.5">
          <GitBranch size={13} style={{ color: 'var(--text-tertiary)' }} />
          <span style={{ color: 'var(--text-secondary)' }}>Default branch:</span>
          <span className="mono font-medium" style={{ color: 'var(--text-primary)' }}>
            {repository.default_branch}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <Clock size={13} style={{ color: 'var(--text-tertiary)' }} />
          <span style={{ color: 'var(--text-secondary)' }}>Last updated:</span>
          <span style={{ color: 'var(--text-primary)' }}>
            {formatRelativeTime(repository.updated_at)}
          </span>
        </div>
      </div>

      {/* Grid: Latest commits and Review history */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Branches & Commits */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
              Latest Commits
            </h2>
            {/* Branch switcher */}
            {branches.length > 0 && (
              <select
                value={selectedBranch}
                onChange={(e) => setSelectedBranch(e.target.value)}
                className="px-2.5 py-1 rounded text-[12px] outline-none"
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-default)',
                  color: 'var(--text-primary)',
                }}
              >
                {branches.map((b) => (
                  <option key={b.name} value={b.name}>
                    {b.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {loadingCommits ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={18} className="animate-spin" style={{ color: 'var(--text-tertiary)' }} />
            </div>
          ) : commits.length === 0 ? (
            <div
              className="p-4 rounded text-center text-[12px]"
              style={{ background: 'var(--bg-surface)', color: 'var(--text-tertiary)' }}
            >
              No commits found for branch {selectedBranch}.
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
              {commits.map((commit) => (
                <div
                  key={commit.sha}
                  className="p-2.5 rounded transition-colors hover:bg-white/5 flex items-start justify-between gap-3"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium leading-snug truncate" style={{ color: 'var(--text-primary)' }}>
                      {commit.message || 'No commit message'}
                    </p>
                    <p className="text-[11px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
                      {commit.author_name} • {formatRelativeTime(commit.date)}
                    </p>
                  </div>
                  <span
                    className="mono text-[11px] px-2 py-0.5 rounded font-medium flex-shrink-0"
                    style={{ background: 'var(--bg-elevated)', color: 'var(--primary-hover)', border: '1px solid var(--border-subtle)' }}
                  >
                    {commit.short_sha}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Review History */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
              Review History ({reviews.length})
            </h2>
            <Link
              href={`/dashboard/reviewer?repo=${repository.id}`}
              className="text-[12px] font-medium hover:underline"
              style={{ color: 'var(--primary-hover)' }}
            >
              + New Review
            </Link>
          </div>

          {reviews.length === 0 ? (
            <div
              className="p-8 rounded text-center text-[12px] flex flex-col items-center gap-2"
              style={{ background: 'var(--bg-surface)', color: 'var(--text-tertiary)' }}
            >
              <GitCommit size={20} />
              <p>No reviews performed on this repository yet.</p>
              <Link
                href={`/dashboard/reviewer?repo=${repository.id}`}
                className="mt-1 px-3 py-1.5 rounded text-[12px] font-medium"
                style={{ background: 'var(--primary-subtle)', color: 'var(--primary-hover)' }}
              >
                Start First Review
              </Link>
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
              {reviews.map((rev) => (
                <div
                  key={rev.id}
                  className="p-3 rounded flex items-center justify-between gap-3"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={rev.status} />
                      <span className="mono text-[12px]" style={{ color: 'var(--text-primary)' }}>
                        {rev.commit_sha.slice(0, 7)}
                      </span>
                    </div>
                    <p className="text-[11px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
                      Branch: {rev.branch} • Started {formatRelativeTime(rev.created_at)}
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <span className="text-[11px] block" style={{ color: 'var(--text-tertiary)' }}>
                      Score
                    </span>
                    <span className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {formatScore(rev.overall_score)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
