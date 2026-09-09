'use client';

import { Search } from 'lucide-react';

interface RepositorySearchProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function RepositorySearch({
  value,
  onChange,
  placeholder = 'Search repositories…',
}: RepositorySearchProps) {
  return (
    <div className="relative">
      <Search
        size={14}
        className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
        style={{ color: 'var(--text-tertiary)' }}
      />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label="Search repositories"
        className="w-full pl-8 pr-3 py-1.5 rounded text-[13px] outline-none transition-colors"
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-default)',
          color: 'var(--text-primary)',
        }}
        onFocus={(e) => {
          e.target.style.borderColor = 'var(--primary-border)';
        }}
        onBlur={(e) => {
          e.target.style.borderColor = 'var(--border-default)';
        }}
      />
    </div>
  );
}
