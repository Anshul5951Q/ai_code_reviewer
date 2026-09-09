'use client';

import { useState, useEffect } from 'react';
import { Loader2, Download, AlertTriangle, RefreshCw, FolderGit2 } from 'lucide-react';
import type { GitHubRepoItem, GitHubRepoFilters } from '@/types/github';
import { getGitHubRepositories, ApiClientError } from '@/lib/api';
import { GitHubRepositoryRow } from './github-repository-row';
import { GitHubRepositoryFilters } from './github-repository-filters';
import { GitHubImportProgress, type ImportItemStatus } from './github-import-progress';

interface GitHubRepositoryListProps {
  importedFullNames: Set<string>;
  onImportRepository: (repo: GitHubRepoItem) => Promise<boolean>;
  onRefreshImported: () => void;
}

export function GitHubRepositoryList({
  importedFullNames,
  onImportRepository,
  onRefreshImported,
}: GitHubRepositoryListProps) {
  const [repos, setRepos] = useState<GitHubRepoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isRateLimited, setIsRateLimited] = useState(false);

  const [filters, setFilters] = useState<GitHubRepoFilters>({
    page: 1,
    limit: 30,
  });
  const [hasMore, setHasMore] = useState(false);

  // Multi-select state
  const [selectedNames, setSelectedNames] = useState<Set<string>>(new Set());

  // Batch import progress state
  const [importProgressOpen, setImportProgressOpen] = useState(false);
  const [importItems, setImportItems] = useState<ImportItemStatus[]>([]);
  const [batchFinished, setBatchFinished] = useState(false);

  useEffect(() => {
    let ignore = false;
    getGitHubRepositories(filters)
      .then((items) => {
        if (!ignore) {
          setRepos(items);
          setHasMore(items.length === (filters.limit ?? 30));
          setError(null);
          setIsRateLimited(false);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          if (err instanceof ApiClientError && err.status === 429) {
            setIsRateLimited(true);
            setError('GitHub has temporarily limited API requests. Please try again later.');
          } else if (err instanceof ApiClientError) {
            setError(err.detail);
          } else {
            setError('Failed to load GitHub repositories.');
          }
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [filters]);

  const handleManualRefresh = async () => {
    setLoading(true);
    try {
      const items = await getGitHubRepositories(filters);
      setRepos(items);
      setHasMore(items.length === (filters.limit ?? 30));
      setError(null);
    } catch (err: unknown) {
      if (err instanceof ApiClientError && err.status === 429) {
        setIsRateLimited(true);
        setError('GitHub has temporarily limited API requests. Please try again later.');
      } else {
        setError('Failed to reload repositories.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (newFilters: Partial<GitHubRepoFilters>) => {
    setFilters((prev) => ({ ...prev, ...newFilters }));
    setSelectedNames(new Set());
  };

  const handleLoadMore = () => {
    const nextPage = (filters.page ?? 1) + 1;
    const updated = { ...filters, page: nextPage };
    setFilters(updated);
    setLoadingMore(true);
    getGitHubRepositories(updated)
      .then((items) => {
        setRepos((prev) => [...prev, ...items]);
        setHasMore(items.length === (updated.limit ?? 30));
      })
      .catch(() => {
        setError('Failed to load more repositories.');
      })
      .finally(() => {
        setLoadingMore(false);
      });
  };

  const handleSelectOne = (fullName: string, selected: boolean) => {
    setSelectedNames((prev) => {
      const next = new Set(prev);
      if (selected) next.add(fullName);
      else next.delete(fullName);
      return next;
    });
  };

  const handleSelectAll = (checked: boolean) => {
    if (!checked) {
      setSelectedNames(new Set());
    } else {
      const unimported = repos
        .filter((r) => !importedFullNames.has(r.full_name))
        .map((r) => r.full_name);
      setSelectedNames(new Set(unimported));
    }
  };

  const handleSingleImport = async (repo: GitHubRepoItem) => {
    await onImportRepository(repo);
    onRefreshImported();
  };

  const handleBatchImport = async () => {
    if (selectedNames.size === 0) return;

    const targets = repos.filter((r) => selectedNames.has(r.full_name));
    const initialItems: ImportItemStatus[] = targets.map((r) => ({
      name: r.full_name,
      status: 'pending',
    }));

    setImportItems(initialItems);
    setImportProgressOpen(true);
    setBatchFinished(false);

    for (let i = 0; i < targets.length; i++) {
      const target = targets[i];
      setImportItems((prev) =>
        prev.map((item, idx) => (idx === i ? { ...item, status: 'importing' } : item)),
      );

      try {
        const success = await onImportRepository(target);
        setImportItems((prev) =>
          prev.map((item, idx) =>
            idx === i ? { ...item, status: success ? 'completed' : 'already_imported' } : item,
          ),
        );
      } catch (err: unknown) {
        const msg = err instanceof ApiClientError ? err.detail : 'Failed';
        setImportItems((prev) =>
          prev.map((item, idx) =>
            idx === i ? { ...item, status: 'failed', error: msg } : item,
          ),
        );
      }
    }

    setBatchFinished(true);
    setSelectedNames(new Set());
    onRefreshImported();
  };

  const unimportedInView = repos.filter((r) => !importedFullNames.has(r.full_name));
  const allSelected = unimportedInView.length > 0 && selectedNames.size === unimportedInView.length;

  return (
    <div className="space-y-4">
      {/* Filters Toolbar */}
      <GitHubRepositoryFilters
        filters={filters}
        onFilterChange={handleFilterChange}
        disabled={loading}
      />

      {/* Batch Actions Bar */}
      {repos.length > 0 && (
        <div
          className="px-4 py-2 rounded-xl flex items-center justify-between text-xs mb-3"
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}
        >
          <label className="flex items-center gap-2 text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={(e) => handleSelectAll(e.target.checked)}
              disabled={unimportedInView.length === 0}
              className="w-4 h-4 rounded border-zinc-700 bg-zinc-800 text-indigo-600 focus:ring-0 focus:ring-offset-0 cursor-pointer disabled:opacity-40"
            />
            <span>Select all available ({unimportedInView.length})</span>
          </label>

          <div className="flex items-center gap-3">
            {selectedNames.size > 0 && (
              <span className="text-zinc-400">
                <span className="font-semibold text-white">{selectedNames.size}</span> selected
              </span>
            )}
            <button
              onClick={() => void handleBatchImport()}
              disabled={selectedNames.size === 0}
              className="px-3 py-1.5 rounded-lg text-white font-medium flex items-center gap-1.5 transition-all disabled:opacity-40"
              style={{ background: 'var(--primary)' }}
            >
              <Download size={13} />
              <span>Import Selected</span>
            </button>
          </div>
        </div>
      )}

      {/* Rate limit error box */}
      {isRateLimited && (
        <div
          className="p-5 rounded-xl flex items-start gap-3"
          style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid var(--critical-border)' }}
        >
          <AlertTriangle size={18} style={{ color: 'var(--critical)' }} className="flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-white">GitHub API limit reached</h4>
            <p className="text-xs text-zinc-400 mt-1">{error}</p>
            <button
              onClick={() => void handleManualRefresh()}
              className="mt-2 px-3 py-1 text-xs font-medium rounded bg-white/10 text-white hover:bg-white/15 transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* General Error State */}
      {!isRateLimited && error && (
        <div
          className="p-5 rounded-xl text-center space-y-2"
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)' }}
        >
          <p className="text-xs text-red-400">{error}</p>
          <button
            onClick={() => void handleManualRefresh()}
            className="px-3 py-1 text-xs rounded bg-zinc-800 text-zinc-300 hover:text-white"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading ? (
        <div className="space-y-2.5">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-16 rounded-xl animate-pulse"
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
            />
          ))}
        </div>
      ) : repos.length === 0 && !error ? (
        <div
          className="p-10 rounded-xl text-center flex flex-col items-center justify-center gap-2"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
        >
          <FolderGit2 size={32} className="text-zinc-500" />
          <p className="text-sm font-medium text-white">No repositories found</p>
          <p className="text-xs text-zinc-400">
            {filters.search
              ? `No repositories matched "${filters.search}"`
              : 'No accessible GitHub repositories match the selected filter.'}
          </p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {repos.map((repo) => (
            <GitHubRepositoryRow
              key={repo.id}
              repo={repo}
              isImported={importedFullNames.has(repo.full_name)}
              isSelected={selectedNames.has(repo.full_name)}
              onSelect={(checked) => handleSelectOne(repo.full_name, checked)}
              onImport={handleSingleImport}
            />
          ))}
        </div>
      )}

      {/* Pagination: Load More */}
      {hasMore && !loading && (
        <div className="pt-2 text-center">
          <button
            onClick={handleLoadMore}
            disabled={loadingMore}
            className="px-4 py-2 rounded-lg text-xs font-medium text-zinc-300 hover:text-white transition-all flex items-center gap-2 mx-auto disabled:opacity-50"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)' }}
          >
            {loadingMore ? (
              <>
                <Loader2 size={13} className="animate-spin" />
                <span>Loading more…</span>
              </>
            ) : (
              <>
                <RefreshCw size={13} />
                <span>Load more repositories</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Batch Import Progress Modal */}
      <GitHubImportProgress
        items={importItems}
        isOpen={importProgressOpen}
        onClose={() => setImportProgressOpen(false)}
        isFinished={batchFinished}
      />
    </div>
  );
}

export default GitHubRepositoryList;
