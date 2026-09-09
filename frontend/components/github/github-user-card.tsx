'use client';

import { useState } from 'react';
import Image from 'next/image';
import { User, LogOut, Loader2 } from 'lucide-react';
import type { GitHubStatusResponse } from '@/types/github';

interface GitHubUserCardProps {
  status: GitHubStatusResponse;
  onDisconnect: () => Promise<void>;
}

export function GitHubUserCard({ status, onDisconnect }: GitHubUserCardProps) {
  const [disconnecting, setDisconnecting] = useState(false);

  const handleDisconnect = async () => {
    if (disconnecting) return;
    setDisconnecting(true);
    try {
      await onDisconnect();
    } finally {
      setDisconnecting(false);
    }
  };

  const username = status.github_login || status.authenticated_user || 'GitHub User';

  return (
    <div
      className="flex items-center justify-between p-3 rounded-xl gap-4"
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="relative w-9 h-9 rounded-full overflow-hidden bg-zinc-800 flex-shrink-0 border border-white/10 flex items-center justify-center">
          {status.avatar_url ? (
            <Image
              src={status.avatar_url}
              alt={username}
              fill
              className="object-cover"
              sizes="36px"
              unoptimized
            />
          ) : (
            <User size={18} className="text-zinc-400" />
          )}
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-white truncate">@{username}</span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Connected
            </span>
          </div>

          {status.rate_limit_remaining !== null && status.rate_limit_remaining !== undefined && (
            <p className="text-[11px] text-zinc-400 mt-0.5">
              API limit: {status.rate_limit_remaining} / {status.rate_limit_limit ?? 5000} requests remaining
            </p>
          )}
        </div>
      </div>

      <button
        onClick={() => void handleDisconnect()}
        disabled={disconnecting}
        className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition-colors flex items-center gap-1.5 flex-shrink-0 disabled:opacity-50"
        title="Disconnect GitHub account"
      >
        {disconnecting ? (
          <Loader2 size={13} className="animate-spin" />
        ) : (
          <LogOut size={13} />
        )}
        <span>Disconnect</span>
      </button>
    </div>
  );
}

export default GitHubUserCard;
