'use client';

import { useEffect, useState, useMemo } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { RotateCw, AlertCircle, CheckCircle2, XCircle, Info, FolderGit2 } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { RepositoryGrid } from '@/components/repositories/repository-grid';
import { RepositorySearch } from '@/components/repositories/repository-search';
import { LoadingState } from '@/components/common/loading-state';
import { GitHubConnection, GitHubIcon } from '@/components/github';
import { GitHubRepositoryList } from '@/components/github/github-repository-list';
import {
  ApiClientError,
  getRepositories,
  createRepository,
  getGitHubStatus,
  disconnectGitHub,
} from '@/lib/api';
import type { Repository, RepositoryVisibility } from '@/types/repository';
import type { GitHubRepoItem, GitHubStatusResponse } from '@/types/github';

export function RepositoriesView() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [activeTab, setActiveTab] = useState<'imported' | 'github'>(() => {
    return searchParams.get('github') === 'connected' ? 'github' : 'imported';
  });

  // Local imported repositories
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(true);
  const [repoError, setRepoError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  // GitHub connection status
  const [githubStatus, setGithubStatus] = useState<GitHubStatusResponse | null>(null);
  const [loadingGithub, setLoadingGithub] = useState(true);

  // Flash banner message from OAuth callback redirect
  const [bannerMessage, setBannerMessage] = useState<{
    type: 'success' | 'warning' | 'error' | 'info';
    title: string;
    description: string;
  } | null>(() => {
    const githubParam = searchParams.get('github');
    const messageParam = searchParams.get('message');
    if (githubParam === 'connected') {
      return {
        type: 'success',
        title: 'GitHub connected successfully',
        description: 'Your account is authorized. You can now browse and import repositories.',
      };
    } else if (githubParam === 'cancelled') {
      return {
        type: 'warning',
        title: 'GitHub connection cancelled',
        description: 'Authorization was not completed. You can try connecting again anytime.',
      };
    } else if (githubParam === 'invalid_state') {
      return {
        type: 'error',
        title: 'Invalid authorization state',
        description: 'GitHub authorization could not be verified. Please restart the connection.',
      };
    } else if (githubParam === 'error') {
      return {
        type: 'error',
        title: 'Unable to connect GitHub',
        description: messageParam ? decodeURIComponent(messageParam) : 'An error occurred during authorization. Please try again.',
      };
    }
    return null;
  });

  // Set of full_names already imported
  const importedFullNames = useMemo(
    () => new Set(repositories.map((r) => r.full_name)),
    [repositories],
  );

  // Clean URL query parameter if present
  useEffect(() => {
    if (searchParams.get('github')) {
      router.replace('/dashboard/repositories');
    }
  }, [searchParams, router]);

  // Initial load
  useEffect(() => {
    let ignore = false;

    getGitHubStatus()
      .then((status) => {
        if (!ignore) {
          setGithubStatus(status);
          setLoadingGithub(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setGithubStatus({ connected: false });
          setLoadingGithub(false);
        }
      });

    getRepositories()
      .then((res) => {
        if (!ignore) {
          setRepositories(res.items);
          setLoadingRepos(false);
        }
      })
      .catch((e: unknown) => {
        if (!ignore) {
          const msg = e instanceof ApiClientError ? e.detail : 'Failed to load repositories';
          setRepoError(msg);
          setLoadingRepos(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  const fetchGitHubStatus = async () => {
    setLoadingGithub(true);
    try {
      const status = await getGitHubStatus();
      setGithubStatus(status);
      if (status.connected) {
        setActiveTab('github');
      }
    } catch {
      setGithubStatus({ connected: false });
    } finally {
      setLoadingGithub(false);
    }
  };

  const fetchRepos = async () => {
    setLoadingRepos(true);
    try {
      const res = await getRepositories();
      setRepositories(res.items);
      setRepoError(null);
    } catch (e: unknown) {
      const msg = e instanceof ApiClientError ? e.detail : 'Failed to load repositories';
      setRepoError(msg);
    } finally {
      setLoadingRepos(false);
    }
  };

  // 4. Import a single repository into database
  const handleImportRepository = async (repo: GitHubRepoItem): Promise<boolean> => {
    try {
      await createRepository({
        name: repo.name,
        full_name: repo.full_name,
        owner: repo.owner,
        default_branch: repo.default_branch,
        visibility: (repo.visibility === 'private' ? 'private' : 'public') as RepositoryVisibility,
        language: repo.language ?? undefined,
        github_id: repo.id,
      });
      await fetchRepos();
      return true;
    } catch (e: unknown) {
      if (e instanceof ApiClientError && e.status === 409) {
        return false; // Already imported
      }
      throw e;
    }
  };

  // 5. Disconnect account
  const handleDisconnect = async () => {
    try {
      await disconnectGitHub();
      setGithubStatus({ connected: false });
      setActiveTab('imported');
      setBannerMessage({
        type: 'info',
        title: 'GitHub Disconnected',
        description: 'Your GitHub connection was removed. Existing imported repositories and historical reviews remain intact.',
      });
    } catch (e: unknown) {
      const msg = e instanceof ApiClientError ? e.detail : 'Failed to disconnect GitHub';
      setBannerMessage({
        type: 'error',
        title: 'Disconnect Failed',
        description: msg,
      });
    }
  };

  const isConnected = githubStatus?.connected === true;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Repositories"
        description="Connect your GitHub account and manage repositories for automated code review."
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                void fetchRepos();
                void fetchGitHubStatus();
              }}
              disabled={loadingRepos || loadingGithub}
              className="p-1.5 rounded transition-colors hover:bg-white/5 disabled:opacity-50"
              style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-default)' }}
              title="Refresh repositories"
              aria-label="Refresh repositories"
            >
              <RotateCw size={14} className={loadingRepos ? 'animate-spin' : ''} />
            </button>
          </div>
        }
      />

      {/* OAuth Notification Banner */}
      {bannerMessage && (
        <div
          className={`p-4 rounded-xl flex items-start justify-between gap-3 animate-fade-in ${
            bannerMessage.type === 'success'
              ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
              : bannerMessage.type === 'warning'
              ? 'bg-amber-500/10 border border-amber-500/30 text-amber-400'
              : bannerMessage.type === 'error'
              ? 'bg-red-500/10 border border-red-500/30 text-red-400'
              : 'bg-indigo-500/10 border border-indigo-500/30 text-indigo-400'
          }`}
        >
          <div className="flex items-start gap-2.5">
            {bannerMessage.type === 'success' && <CheckCircle2 size={16} className="mt-0.5 flex-shrink-0" />}
            {bannerMessage.type === 'warning' && <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />}
            {bannerMessage.type === 'error' && <XCircle size={16} className="mt-0.5 flex-shrink-0" />}
            {bannerMessage.type === 'info' && <Info size={16} className="mt-0.5 flex-shrink-0" />}
            <div>
              <p className="text-xs font-semibold text-white">{bannerMessage.title}</p>
              <p className="text-xs text-zinc-300 mt-0.5">{bannerMessage.description}</p>
            </div>
          </div>

          <button
            onClick={() => setBannerMessage(null)}
            className="text-zinc-400 hover:text-white p-1 rounded transition-colors"
            aria-label="Dismiss banner"
          >
            ✕
          </button>
        </div>
      )}

      {/* GitHub Connection Status Bar */}
      <GitHubConnection
        status={githubStatus}
        loading={loadingGithub}
        onDisconnect={handleDisconnect}
        onRefreshStatus={fetchGitHubStatus}
        onViewRepositories={() => setActiveTab(activeTab === 'github' ? 'imported' : 'github')}
        isViewingRemote={activeTab === 'github'}
      />

      {/* Repository Section Navigation (Separating Local vs Remote) */}
      <div className="flex items-center gap-2 border-b border-white/5 pb-2">
        <button
          onClick={() => setActiveTab('imported')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-2 ${
            activeTab === 'imported'
              ? 'bg-white/10 text-white font-semibold'
              : 'text-zinc-400 hover:text-white'
          }`}
        >
          <FolderGit2 size={14} />
          <span>Imported Repositories</span>
          <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-white/10 text-zinc-300">
            {repositories.length}
          </span>
        </button>

        {isConnected && (
          <button
            onClick={() => setActiveTab('github')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-2 ${
              activeTab === 'github'
                ? 'bg-white/10 text-white font-semibold'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            <GitHubIcon size={14} />
            <span>GitHub Repositories</span>
          </button>
        )}
      </div>

      {/* Tab 1: Imported Repositories */}
      {activeTab === 'imported' && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex-1 max-w-xs">
              <RepositorySearch
                value={search}
                onChange={setSearch}
                placeholder="Search imported repositories…"
              />
            </div>
          </div>

          {loadingRepos ? (
            <LoadingState message="Loading repositories..." />
          ) : repoError ? (
            <div
              className="p-6 rounded-lg text-center my-6 flex flex-col items-center justify-center gap-2"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)' }}
            >
              <AlertCircle size={24} style={{ color: 'var(--critical)' }} />
              <p className="text-[13px] font-medium" style={{ color: 'var(--text-primary)' }}>
                Unable to load repositories
              </p>
              <p className="text-[12px] max-w-md" style={{ color: 'var(--text-secondary)' }}>
                {repoError}
              </p>
              <button
                onClick={() => void fetchRepos()}
                className="mt-2 px-3 py-1.5 rounded text-[12px] font-medium transition-colors"
                style={{ background: 'var(--primary)', color: 'white' }}
              >
                Try Again
              </button>
            </div>
          ) : repositories.length === 0 ? (
            <div
              className="p-12 rounded-xl text-center flex flex-col items-center justify-center gap-3"
              style={{ background: 'var(--bg-surface)', border: '1px dashed var(--border-default)' }}
            >
              <FolderGit2 size={36} className="text-zinc-500" />
              <div className="max-w-md">
                <h3 className="text-sm font-semibold text-white">No repositories imported yet</h3>
                <p className="text-xs text-zinc-400 mt-1">
                  {isConnected
                    ? 'Switch to the "GitHub Repositories" tab above to import projects for analysis.'
                    : 'Connect your GitHub account above to view and import your repositories.'}
                </p>
              </div>
              {isConnected && (
                <button
                  onClick={() => setActiveTab('github')}
                  className="px-3.5 py-1.5 text-xs font-medium rounded-lg text-white mt-2"
                  style={{ background: 'var(--primary)' }}
                >
                  Browse GitHub Repositories
                </button>
              )}
            </div>
          ) : (
            <RepositoryGrid
              repositories={repositories}
              searchQuery={search}
              onRefresh={fetchRepos}
            />
          )}
        </div>
      )}

      {/* Tab 2: Remote GitHub Repositories */}
      {activeTab === 'github' && isConnected && (
        <GitHubRepositoryList
          importedFullNames={importedFullNames}
          onImportRepository={handleImportRepository}
          onRefreshImported={fetchRepos}
        />
      )}
    </div>
  );
}

export default RepositoriesView;
