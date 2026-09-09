'use client';

import { useState } from 'react';
import { Lock, Globe, Code2, Clock, ScanSearch, ExternalLink, Trash2, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { LabelBadge } from '@/components/common/status-badge';
import { formatRelativeTime, formatScore } from '@/lib/utils';
import { deleteRepository } from '@/lib/api';
import type { Repository } from '@/types/repository';

interface RepositoryCardProps {
  repository: Repository;
  onDeleted?: () => void;
}

export function RepositoryCard({ repository, onDeleted }: RepositoryCardProps) {
  const isPrivate = repository.visibility === 'private';
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function handleDelete() {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setDeleting(true);
    try {
      await deleteRepository(repository.id);
      onDeleted?.();
    } catch {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  return (
    <div
      className="card flex flex-col gap-3 hover:border-white/10 transition-all duration-150"
      style={{ borderColor: 'var(--border-subtle)' }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Link
              href={`/dashboard/repositories/${repository.id}`}
              className="text-[13px] font-semibold truncate hover:underline"
              style={{ color: 'var(--text-primary)' }}
            >
              {repository.name}
            </Link>
            <span title={isPrivate ? 'Private' : 'Public'}>
              {isPrivate ? (
                <Lock size={11} style={{ color: 'var(--text-disabled)' }} />
              ) : (
                <Globe size={11} style={{ color: 'var(--text-disabled)' }} />
              )}
            </span>
          </div>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
            {repository.owner}
          </p>
        </div>
        <LabelBadge label={repository.visibility} variant="outline" />
      </div>

      {/* Meta */}
      <div className="flex items-center gap-3 flex-wrap">
        {repository.language && (
          <span className="flex items-center gap-1 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
            <Code2 size={11} />
            {repository.language}
          </span>
        )}
        <span className="flex items-center gap-1 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
          <Clock size={11} />
          Updated {formatRelativeTime(repository.updated_at)}
        </span>
      </div>

      {/* Scores and actions row */}
      <div
        className="flex items-center gap-4 pt-2"
        style={{ borderTop: '1px solid var(--border-subtle)' }}
      >
        <div>
          <span className="block text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-disabled)' }}>
            Security
          </span>
          <span className="text-[13px] font-semibold tabular-nums" style={{ color: 'var(--text-primary)' }}>
            {formatScore(null)}
          </span>
        </div>
        <div>
          <span className="block text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-disabled)' }}>
            Quality
          </span>
          <span className="text-[13px] font-semibold tabular-nums" style={{ color: 'var(--text-primary)' }}>
            {formatScore(null)}
          </span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          {confirmDelete ? (
            <div className="flex items-center gap-1">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-2 py-1 rounded text-[11px] font-medium transition-colors"
                style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444' }}
              >
                {deleting ? <Loader2 size={11} className="animate-spin" /> : 'Confirm'}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="px-1.5 py-1 rounded text-[11px]"
                style={{ color: 'var(--text-tertiary)' }}
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={handleDelete}
              className="p-1 rounded transition-colors hover:bg-white/5"
              style={{ color: 'var(--text-tertiary)' }}
              title="Delete repository"
              aria-label="Delete repository"
            >
              <Trash2 size={13} />
            </button>
          )}

          <Link
            href={`/dashboard/reviewer?repo=${repository.id}`}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-[12px] font-medium transition-colors"
            style={{
              background: 'var(--primary-subtle)',
              color: 'var(--primary-hover)',
              border: '1px solid var(--primary-border)',
            }}
            aria-label={`Analyze ${repository.name}`}
          >
            <ScanSearch size={11} />
            Analyze
          </Link>
          <a
            href={`https://github.com/${repository.full_name}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1 rounded transition-colors hover:bg-white/5"
            style={{ color: 'var(--text-tertiary)' }}
            aria-label={`Open ${repository.name} on GitHub`}
          >
            <ExternalLink size={13} />
          </a>
        </div>
      </div>
    </div>
  );
}
