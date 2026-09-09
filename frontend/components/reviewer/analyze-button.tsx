'use client';

import { ScanSearch, Loader2 } from 'lucide-react';
import Link from 'next/link';

interface AnalyzeButtonProps {
  disabled?: boolean;
  loading?: boolean;
  reason?: string;
  onClick?: () => void;
}

export function AnalyzeButton({
  disabled = true,
  loading = false,
  reason = 'Connect a repository first',
  onClick,
}: AnalyzeButtonProps) {
  if (disabled) {
    return (
      <div>
        <button
          type="button"
          disabled
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded text-[13px] font-medium cursor-not-allowed"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-disabled)',
          }}
          aria-disabled="true"
          title={reason}
        >
          <ScanSearch size={14} />
          Analyze Repository
        </button>
        <p className="text-center text-[11px] mt-2" style={{ color: 'var(--text-disabled)' }}>
          {reason} •{' '}
          <Link
            href="/dashboard/repositories"
            className="underline underline-offset-2 transition-colors hover:text-white"
          >
            Go to Repositories
          </Link>
        </p>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded text-[13px] font-medium transition-all cursor-pointer"
      style={{
        background: 'var(--primary)',
        color: 'white',
        opacity: loading ? 0.75 : 1,
      }}
    >
      {loading ? (
        <>
          <Loader2 size={14} className="animate-spin" />
          Queueing Code Review...
        </>
      ) : (
        <>
          <ScanSearch size={14} />
          Start Code Review
        </>
      )}
    </button>
  );
}
