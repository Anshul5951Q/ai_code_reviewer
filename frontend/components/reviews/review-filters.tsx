'use client';

import { Search, ChevronDown } from 'lucide-react';
import type { ReviewFilters } from '@/types/review';

const STATUS_OPTIONS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'queued', label: 'Queued' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
] as const;

interface ReviewFiltersBarProps {
  filters: ReviewFilters;
  onChange: (filters: ReviewFilters) => void;
}

export function ReviewFiltersBar({ filters, onChange }: ReviewFiltersBarProps) {
  const update = (partial: Partial<ReviewFilters>) =>
    onChange({ ...filters, ...partial });

  const inputStyle = {
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border-default)',
    color: 'var(--text-primary)',
    borderRadius: 6,
    padding: '6px 10px',
    fontSize: 13,
    outline: 'none',
  };

  return (
    <div className="flex items-center gap-3 flex-wrap mb-4">
      {/* Search */}
      <div className="relative flex-1 min-w-[160px] max-w-xs">
        <Search
          size={13}
          className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
          style={{ color: 'var(--text-tertiary)' }}
        />
        <input
          type="search"
          value={filters.search}
          onChange={(e) => update({ search: e.target.value })}
          placeholder="Search reviews…"
          aria-label="Search reviews"
          style={{ ...inputStyle, paddingLeft: 32, width: '100%' }}
        />
      </div>

      {/* Status filter */}
      <div className="relative">
        <select
          value={filters.status}
          onChange={(e) => update({ status: e.target.value as ReviewFilters['status'] })}
          aria-label="Filter by status"
          style={{ ...inputStyle, paddingRight: 28, appearance: 'none', cursor: 'pointer' }}
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown
          size={12}
          className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none"
          style={{ color: 'var(--text-tertiary)' }}
        />
      </div>
    </div>
  );
}
