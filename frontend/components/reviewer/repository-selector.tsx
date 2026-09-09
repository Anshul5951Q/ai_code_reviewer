'use client';

import { GitBranch, Loader2 } from 'lucide-react';
import type { Repository } from '@/types/repository';

interface RepositorySelectorProps {
  repositories: Repository[];
  selectedId: string;
  onSelect: (repoId: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

export function RepositorySelector({
  repositories,
  selectedId,
  onSelect,
  disabled = false,
  loading = false,
}: RepositorySelectorProps) {
  return (
    <div>
      <label
        htmlFor="repository-selector"
        className="block text-[12px] font-medium mb-1.5"
        style={{ color: 'var(--text-secondary)' }}
      >
        Repository
      </label>
      <div className="relative">
        <select
          id="repository-selector"
          value={selectedId}
          onChange={(e) => onSelect(e.target.value)}
          disabled={disabled || loading || repositories.length === 0}
          className="w-full px-3 py-2 rounded text-[13px] outline-none appearance-none cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)',
            color: 'var(--text-primary)',
          }}
        >
          {repositories.length === 0 ? (
            <option value="">No repositories connected</option>
          ) : (
            <>
              <option value="">Select a repository...</option>
              {repositories.map((repo) => (
                <option key={repo.id} value={repo.id}>
                  {repo.full_name} ({repo.default_branch})
                </option>
              ))}
            </>
          )}
        </select>
        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
          {loading ? (
            <Loader2 size={13} className="animate-spin" style={{ color: 'var(--text-tertiary)' }} />
          ) : (
            <GitBranch size={13} style={{ color: 'var(--text-tertiary)' }} />
          )}
        </div>
      </div>
      {repositories.length === 0 && !loading && (
        <p className="text-[11px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
          No repositories found in database. Connect GitHub on the Repositories page to track projects.
        </p>
      )}
    </div>
  );
}
