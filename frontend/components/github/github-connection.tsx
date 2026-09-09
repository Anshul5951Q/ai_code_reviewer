'use client';

import { useState } from 'react';
import Image from 'next/image';
import { Plus, LogOut, Loader2, RefreshCw } from 'lucide-react';
import type { GitHubStatusResponse } from '@/types/github';
import { GitHubConnectModal } from './github-connect-modal';
import { GitHubIcon } from './github-icon';

interface GitHubConnectionProps {
  status: GitHubStatusResponse | null;
  loading: boolean;
  onDisconnect: () => Promise<void>;
  onRefreshStatus?: () => void;
  onViewRepositories?: () => void;
  isViewingRemote?: boolean;
}

export function GitHubConnection({
  status,
  loading,
  onDisconnect,
  onRefreshStatus,
  onViewRepositories,
  isViewingRemote = false,
}: GitHubConnectionProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  const isConnected = status?.connected === true;
  const username = status?.github_login || status?.authenticated_user || 'user';

  const handleDisconnect = async () => {
    if (disconnecting) return;
    setDisconnecting(true);
    try {
      await onDisconnect();
    } finally {
      setDisconnecting(false);
    }
  };

  if (loading) {
    return (
      <div
        className="p-4 rounded-xl flex items-center justify-between animate-pulse mb-6"
        style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-zinc-800" />
          <div className="space-y-1.5">
            <div className="w-24 h-3 bg-zinc-800 rounded" />
            <div className="w-48 h-2.5 bg-zinc-800 rounded" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div
        className="p-4 rounded-xl mb-6 flex flex-wrap items-center justify-between gap-4 transition-colors"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-default)',
        }}
      >
        {/* Left Side: Info */}
        <div className="flex items-center gap-3.5 min-w-0">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 relative overflow-hidden"
            style={{
              background: isConnected ? 'var(--bg-elevated)' : 'rgba(255,255,255,0.04)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            {isConnected && status.avatar_url ? (
              <Image
                src={status.avatar_url}
                alt={username}
                fill
                className="object-cover"
                sizes="40px"
                unoptimized
              />
            ) : (
              <GitHubIcon size={20} className="text-zinc-300" />
            )}
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-white">GitHub</h2>
              {isConnected ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Connected as @{username}
                </span>
              ) : (
                <span className="text-[11px] px-2 py-0.5 rounded text-zinc-400 bg-white/5">
                  Disconnected
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              {isConnected
                ? `Import repositories from your GitHub account for automated review`
                : 'Connect your GitHub account to import repositories and select branches'}
            </p>
          </div>
        </div>

        {/* Right Side: Actions */}
        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              {onViewRepositories && (
                <button
                  onClick={onViewRepositories}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg text-white transition-colors"
                  style={{
                    background: isViewingRemote ? 'var(--bg-elevated)' : 'var(--primary)',
                    border: '1px solid var(--primary-border)',
                  }}
                >
                  {isViewingRemote ? 'View Imported' : 'Browse GitHub Repositories'}
                </button>
              )}

              {onRefreshStatus && (
                <button
                  onClick={onRefreshStatus}
                  className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
                  title="Refresh connection status"
                >
                  <RefreshCw size={14} />
                </button>
              )}

              <button
                onClick={() => void handleDisconnect()}
                disabled={disconnecting}
                className="px-2.5 py-1.5 text-xs font-medium rounded-lg text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition-colors flex items-center gap-1.5 disabled:opacity-50"
              >
                {disconnecting ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <LogOut size={13} />
                )}
                <span>Disconnect</span>
              </button>
            </>
          ) : (
            <button
              onClick={() => setModalOpen(true)}
              className="px-3.5 py-1.5 text-xs font-medium rounded-lg text-white flex items-center gap-1.5 shadow-sm transition-all"
              style={{ background: 'var(--primary)' }}
            >
              <Plus size={14} />
              <span>Connect GitHub</span>
            </button>
          )}
        </div>
      </div>

      <GitHubConnectModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={() => {
          setModalOpen(false);
          onRefreshStatus?.();
        }}
        oauthConfigured={status?.oauth_configured}
      />
    </>
  );
}

export default GitHubConnection;
