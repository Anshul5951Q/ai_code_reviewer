'use client';

import { Search } from 'lucide-react';
import type { GitHubRepoFilters } from '@/types/github';

interface GitHubRepositoryFiltersProps {
  filters: GitHubRepoFilters;
  onFilterChange: (filters: Partial<GitHubRepoFilters>) => void;
  disabled?: boolean;
}

type TabType = 'all' | 'owner' | 'member' | 'public' | 'private';

export function GitHubRepositoryFilters({
  filters,
  onFilterChange,
  disabled = false,
}: GitHubRepositoryFiltersProps) {
  // Determine current active filter tab
  let activeTab: TabType = 'all';
  if (filters.visibility === 'public') activeTab = 'public';
  else if (filters.visibility === 'private') activeTab = 'private';
  else if (filters.type === 'owner' || filters.affiliation === 'owner') activeTab = 'owner';
  else if (filters.type === 'member' || filters.affiliation === 'organization_member') activeTab = 'member';

  const handleTabClick = (tab: TabType) => {
    if (tab === 'all') {
      onFilterChange({ type: undefined, visibility: undefined, affiliation: undefined, page: 1 });
    } else if (tab === 'public') {
      onFilterChange({ type: undefined, visibility: 'public', affiliation: undefined, page: 1 });
    } else if (tab === 'private') {
      onFilterChange({ type: undefined, visibility: 'private', affiliation: undefined, page: 1 });
    } else if (tab === 'owner') {
      onFilterChange({ type: 'owner', visibility: undefined, affiliation: 'owner', page: 1 });
    } else if (tab === 'member') {
      onFilterChange({ type: 'member', visibility: undefined, affiliation: 'organization_member', page: 1 });
    }
  };

  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mb-4">
      {/* Filter Tabs */}
      <div
        className="inline-flex p-1 rounded-lg gap-1 border border-white/5"
        style={{ background: 'var(--bg-elevated)' }}
      >
        <button
          onClick={() => handleTabClick('all')}
          disabled={disabled}
          className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
            activeTab === 'all'
              ? 'bg-white/10 text-white shadow-sm'
              : 'text-zinc-400 hover:text-white'
          }`}
        >
          All
        </button>
        <button
          onClick={() => handleTabClick('owner')}
          disabled={disabled}
          className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
            activeTab === 'owner'
              ? 'bg-white/10 text-white shadow-sm'
              : 'text-zinc-400 hover:text-white'
          }`}
        >
          Owned
        </button>
        <button
          onClick={() => handleTabClick('member')}
          disabled={disabled}
          className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
            activeTab === 'member'
              ? 'bg-white/10 text-white shadow-sm'
              : 'text-zinc-400 hover:text-white'
          }`}
        >
          Organization
        </button>
        <button
          onClick={() => handleTabClick('public')}
          disabled={disabled}
          className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
            activeTab === 'public'
              ? 'bg-white/10 text-white shadow-sm'
              : 'text-zinc-400 hover:text-white'
          }`}
        >
          Public
        </button>
        <button
          onClick={() => handleTabClick('private')}
          disabled={disabled}
          className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
            activeTab === 'private'
              ? 'bg-white/10 text-white shadow-sm'
              : 'text-zinc-400 hover:text-white'
          }`}
        >
          Private
        </button>
      </div>

      {/* Search Input */}
      <div className="relative flex-1 max-w-xs">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none"
        />
        <input
          type="text"
          value={filters.search ?? ''}
          onChange={(e) => onFilterChange({ search: e.target.value, page: 1 })}
          placeholder="Search repositories…"
          disabled={disabled}
          className="w-full pl-8 pr-3 py-1.5 rounded-lg text-xs text-white placeholder-zinc-500 transition-colors focus:outline-none focus:border-indigo-500/50"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-subtle)',
          }}
        />
      </div>
    </div>
  );
}

export default GitHubRepositoryFilters;
