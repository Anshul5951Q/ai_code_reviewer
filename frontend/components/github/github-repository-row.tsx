'use client';

import { useState } from 'react';
import { Lock, Globe, Check, Loader2, Download } from 'lucide-react';
import type { GitHubRepoItem } from '@/types/github';
import { formatRelativeTime } from '@/lib/utils';

interface GitHubRepositoryRowProps {
  repo: GitHubRepoItem;
  isImported: boolean;
  isSelected: boolean;
  onSelect: (selected: boolean) => void;
  onImport: (repo: GitHubRepoItem) => Promise<void>;
}

export function GitHubRepositoryRow({
  repo,
  isImported,
  isSelected,
  onSelect,
  onImport,
}: GitHubRepositoryRowProps) {
  const [importing, setImporting] = useState(false);

  const handleImport = async () => {
    if (importing || isImported) return;
    setImporting(true);
    try {
      await onImport(repo);
    } finally {
      setImporting(false);
    }
  };

  const isPrivate = repo.visibility === 'private';

  return (
    <div
      className={`p-3.5 rounded-xl transition-all flex items-center justify-between gap-4 ${
        isSelected ? 'border-indigo-500/40 bg-indigo-500/[0.03]' : 'hover:border-zinc-700'
      }`}
      style={{
        background: 'var(--bg-surface)',
        border: isSelected ? '1px solid var(--primary-border)' : '1px solid var(--border-subtle)',
      }}
    >
      {/* Left: Checkbox + Info */}
      <div className="flex items-center gap-3.5 min-w-0">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={(e) => onSelect(e.target.checked)}
          disabled={isImported}
          className="w-4 h-4 rounded border-zinc-700 bg-zinc-800 text-indigo-600 focus:ring-0 focus:ring-offset-0 cursor-pointer disabled:opacity-30"
          aria-label={`Select ${repo.full_name}`}
        />

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-white truncate font-mono">
              {repo.full_name}
            </span>
            <span
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                isPrivate
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
              }`}
            >
              {isPrivate ? <Lock size={10} /> : <Globe size={10} />}
              <span>{repo.visibility}</span>
            </span>
          </div>

          <div className="flex items-center gap-3 text-[11px] text-zinc-400 mt-1">
            {repo.language && (
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                <span>{repo.language}</span>
              </span>
            )}
            {repo.updated_at && (
              <span>Updated {formatRelativeTime(repo.updated_at)}</span>
            )}
          </div>
        </div>
      </div>

      {/* Right: Import Action */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {isImported ? (
          <span className="px-2.5 py-1 text-xs font-medium rounded-lg text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-1">
            <Check size={13} />
            <span>Imported</span>
          </span>
        ) : (
          <button
            onClick={() => void handleImport()}
            disabled={importing}
            className="px-3 py-1.5 text-xs font-medium rounded-lg text-white transition-all flex items-center gap-1.5 disabled:opacity-50"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)' }}
          >
            {importing ? (
              <>
                <Loader2 size={13} className="animate-spin text-zinc-400" />
                <span>Importing…</span>
              </>
            ) : (
              <>
                <Download size={13} className="text-zinc-400" />
                <span>Import</span>
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}

export default GitHubRepositoryRow;
