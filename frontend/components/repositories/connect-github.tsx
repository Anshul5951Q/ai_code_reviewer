'use client';

import { useCallback, useState } from 'react';
import { GitBranch, X, Check, Loader2, Search, AlertCircle, Plus, ShieldCheck } from 'lucide-react';
import {
  ApiClientError,
  createRepository,
  getGitHubRepositories,
  getGitHubStatus,
} from '@/lib/api';
import type { GitHubRepoItem, GitHubStatusResponse } from '@/types/github';
import type { RepositoryVisibility } from '@/types/repository';

interface ConnectGithubProps {
  variant?: 'button' | 'inline';
  onRepositoryImported?: () => void;
}

export function ConnectGithub({ variant = 'button', onRepositoryImported }: ConnectGithubProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<GitHubStatusResponse | null>(null);
  const [remoteRepos, setRemoteRepos] = useState<GitHubRepoItem[]>([]);
  const [importingId, setImportingId] = useState<number | string | null>(null);
  const [customRepo, setCustomRepo] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadGitHubData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const statusRes = await getGitHubStatus();
      setStatus(statusRes);

      try {
        const reposRes = await getGitHubRepositories({ per_page: 20 });
        setRemoteRepos(reposRes);
      } catch {
        setRemoteRepos([]);
      }
    } catch (e: unknown) {
      const msg = e instanceof ApiClientError ? e.detail : 'Failed to connect to backend GitHub service';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  function handleOpenModal() {
    setModalOpen(true);
    loadGitHubData();
  }

  async function handleImport(repo: GitHubRepoItem) {
    setImportingId(repo.id);
    setError(null);
    try {
      await createRepository({
        name: repo.name,
        full_name: repo.full_name,
        owner: repo.owner,
        default_branch: repo.default_branch,
        visibility: repo.visibility as RepositoryVisibility,
        language: repo.language,
        github_id: repo.id,
      });
      setSuccessMsg(`Imported ${repo.full_name} successfully!`);
      onRepositoryImported?.();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (e: unknown) {
      const msg = e instanceof ApiClientError ? e.detail : `Failed to import ${repo.full_name}`;
      setError(msg);
    } finally {
      setImportingId(null);
    }
  }

  async function handleCustomImport(e: React.FormEvent) {
    e.preventDefault();
    if (!customRepo.trim() || !customRepo.includes('/')) {
      setError('Please provide a valid repository name in the format owner/repo');
      return;
    }
    setImportingId('custom');
    setError(null);
    const [owner, repoName] = customRepo.trim().split('/');
    try {
      await createRepository({
        name: repoName,
        full_name: customRepo.trim(),
        owner,
        default_branch: 'main',
        visibility: 'public',
      });
      setSuccessMsg(`Imported ${customRepo.trim()} successfully!`);
      setCustomRepo('');
      onRepositoryImported?.();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (e: unknown) {
      const msg = e instanceof ApiClientError ? e.detail : `Failed to import ${customRepo}`;
      setError(msg);
    } finally {
      setImportingId(null);
    }
  }

  return (
    <>
      <button
        onClick={handleOpenModal}
        className="flex items-center gap-2 px-3 py-1.5 rounded text-[13px] font-medium transition-all"
        style={{
          background: variant === 'button' ? 'var(--primary)' : 'var(--bg-elevated)',
          color: 'white',
          border: variant === 'inline' ? '1px solid var(--border-default)' : 'none',
        }}
        aria-label="Connect GitHub account"
      >
        <GitBranch size={13} />
        Connect GitHub
      </button>

      {/* GitHub Integration Modal */}
      {modalOpen && (
        <>
          <div
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            onClick={() => setModalOpen(false)}
            aria-hidden="true"
          />
          <div
            className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[520px] max-w-[calc(100vw-32px)] max-h-[85vh] overflow-y-auto rounded-xl p-6"
            role="dialog"
            aria-modal="true"
            aria-labelledby="github-modal-title"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-default)',
            }}
          >
            {/* Close button */}
            <button
              onClick={() => setModalOpen(false)}
              className="absolute top-4 right-4 p-1 rounded transition-colors hover:bg-white/5"
              style={{ color: 'var(--text-tertiary)' }}
              aria-label="Close"
            >
              <X size={16} />
            </button>

            {/* Header */}
            <div className="flex items-center gap-3 mb-3">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-default)' }}
              >
                <GitBranch size={18} style={{ color: 'var(--text-primary)' }} />
              </div>
              <div>
                <h2
                  id="github-modal-title"
                  className="text-[15px] font-semibold"
                  style={{ color: 'var(--text-primary)' }}
                >
                  GitHub Integration
                </h2>
                <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                  Connect repositories to enable multi-agent security analysis.
                </p>
              </div>
            </div>

            {/* Status indicator */}
            {status && (
              <div
                className="flex items-center justify-between p-3 rounded mb-4 text-[12px]"
                style={{
                  background: status.connected ? 'rgba(16, 185, 129, 0.1)' : 'var(--bg-surface)',
                  border: `1px solid ${status.connected ? 'rgba(16, 185, 129, 0.2)' : 'var(--border-subtle)'}`,
                }}
              >
                <div className="flex items-center gap-2">
                  <ShieldCheck
                    size={14}
                    style={{ color: status.connected ? 'var(--success)' : 'var(--text-tertiary)' }}
                  />
                  <span style={{ color: 'var(--text-primary)' }}>
                    {status.connected
                      ? `Connected as @${status.authenticated_user}`
                      : 'Public GitHub Access'}
                  </span>
                </div>
                {status.rate_limit_remaining !== null && status.rate_limit_remaining !== undefined && (
                  <span className="mono text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                    Rate limit: {status.rate_limit_remaining}/{status.rate_limit_limit}
                  </span>
                )}
              </div>
            )}

            {/* Feedback messages */}
            {error && (
              <div
                className="flex items-center gap-2 p-2.5 rounded mb-3 text-[12px]"
                style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.2)' }}
              >
                <AlertCircle size={14} className="flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
            {successMsg && (
              <div
                className="flex items-center gap-2 p-2.5 rounded mb-3 text-[12px]"
                style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.2)' }}
              >
                <Check size={14} className="flex-shrink-0" />
                <span>{successMsg}</span>
              </div>
            )}

            {/* Manual import by name */}
            <form onSubmit={handleCustomImport} className="mb-5">
              <label
                htmlFor="import-by-name"
                className="block text-[12px] font-medium mb-1.5"
                style={{ color: 'var(--text-secondary)' }}
              >
                Import Repository by Name
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search
                    size={13}
                    className="absolute left-3 top-1/2 -translate-y-1/2"
                    style={{ color: 'var(--text-tertiary)' }}
                  />
                  <input
                    id="import-by-name"
                    type="text"
                    value={customRepo}
                    onChange={(e) => setCustomRepo(e.target.value)}
                    placeholder="e.g. facebook/react or octocat/Hello-World"
                    className="w-full pl-8 pr-3 py-1.5 rounded text-[12px] outline-none transition-colors"
                    style={{
                      background: 'var(--bg-surface)',
                      border: '1px solid var(--border-default)',
                      color: 'var(--text-primary)',
                    }}
                  />
                </div>
                <button
                  type="submit"
                  disabled={importingId === 'custom' || !customRepo.trim()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[12px] font-medium transition-all"
                  style={{
                    background: 'var(--primary)',
                    color: 'white',
                    opacity: !customRepo.trim() ? 0.6 : 1,
                  }}
                >
                  {importingId === 'custom' ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Plus size={13} />
                  )}
                  Import
                </button>
              </div>
            </form>

            {/* Remote repositories list */}
            <div>
              <h3 className="text-[12px] font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                Accessible Repositories
              </h3>

              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 size={20} className="animate-spin" style={{ color: 'var(--text-tertiary)' }} />
                </div>
              ) : remoteRepos.length === 0 ? (
                <div
                  className="p-4 rounded text-center text-[12px]"
                  style={{ background: 'var(--bg-surface)', color: 'var(--text-tertiary)' }}
                >
                  No remote repositories listed. Use the import box above to track any public or private repository.
                </div>
              ) : (
                <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  {remoteRepos.map((repo) => (
                    <div
                      key={repo.id}
                      className="flex items-center justify-between p-2.5 rounded transition-colors hover:bg-white/5"
                      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
                    >
                      <div className="min-w-0 flex-1 mr-3">
                        <p className="text-[13px] font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                          {repo.full_name}
                        </p>
                        <p className="text-[11px] truncate" style={{ color: 'var(--text-tertiary)' }}>
                          {repo.language ? `${repo.language} • ` : ''}Default branch: {repo.default_branch}
                        </p>
                      </div>
                      <button
                        onClick={() => handleImport(repo)}
                        disabled={importingId === repo.id}
                        className="flex items-center gap-1 px-2.5 py-1 rounded text-[12px] font-medium transition-all"
                        style={{
                          background: 'var(--primary-subtle)',
                          color: 'var(--primary-hover)',
                          border: '1px solid var(--primary-border)',
                        }}
                      >
                        {importingId === repo.id ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Plus size={12} />
                        )}
                        Track
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}
