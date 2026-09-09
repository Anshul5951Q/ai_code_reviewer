'use client';

import { GitBranch, Loader2 } from 'lucide-react';
import type { GitHubBranch } from '@/types/github';

interface BranchSelectorProps {
  branches: GitHubBranch[];
  selectedBranch: string;
  onSelect: (branch: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

export function BranchSelector({
  branches,
  selectedBranch,
  onSelect,
  disabled = true,
  loading = false,
}: BranchSelectorProps) {
  return (
    <div>
      <label
        htmlFor="branch-selector"
        className="block text-[12px] font-medium mb-1.5"
        style={{ color: 'var(--text-secondary)' }}
      >
        Branch
      </label>
      <div className="relative">
        <select
          id="branch-selector"
          value={selectedBranch}
          onChange={(e) => onSelect(e.target.value)}
          disabled={disabled || loading || branches.length === 0}
          className="w-full px-3 py-2 rounded text-[13px] outline-none appearance-none cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)',
            color: 'var(--text-primary)',
          }}
        >
          {branches.length === 0 ? (
            <option value="">{loading ? 'Loading branches...' : 'No branches'}</option>
          ) : (
            branches.map((b) => (
              <option key={b.name} value={b.name}>
                {b.name}
              </option>
            ))
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
    </div>
  );
}
