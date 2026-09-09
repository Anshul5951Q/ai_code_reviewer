'use client';

import { GitCommit, Loader2 } from 'lucide-react';
import type { GitHubCommit } from '@/types/github';

interface CommitSelectorProps {
  commits: GitHubCommit[];
  selectedSha: string;
  onSelect: (sha: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

export function CommitSelector({
  commits,
  selectedSha,
  onSelect,
  disabled = true,
  loading = false,
}: CommitSelectorProps) {
  return (
    <div>
      <label
        htmlFor="commit-selector"
        className="block text-[12px] font-medium mb-1.5"
        style={{ color: 'var(--text-secondary)' }}
      >
        Commit
      </label>
      <div className="relative">
        <select
          id="commit-selector"
          value={selectedSha}
          onChange={(e) => onSelect(e.target.value)}
          disabled={disabled || loading || commits.length === 0}
          className="w-full px-3 py-2 rounded text-[13px] outline-none appearance-none cursor-pointer disabled:cursor-not-allowed disabled:opacity-60 mono"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)',
            color: 'var(--text-primary)',
          }}
        >
          {commits.length === 0 ? (
            <option value="">{loading ? 'Loading commits...' : 'No commits'}</option>
          ) : (
            commits.map((c) => (
              <option key={c.sha} value={c.sha}>
                {c.short_sha} — {c.message.length > 32 ? `${c.message.slice(0, 32)}…` : c.message}
              </option>
            ))
          )}
        </select>
        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
          {loading ? (
            <Loader2 size={13} className="animate-spin" style={{ color: 'var(--text-tertiary)' }} />
          ) : (
            <GitCommit size={13} style={{ color: 'var(--text-tertiary)' }} />
          )}
        </div>
      </div>
    </div>
  );
}
