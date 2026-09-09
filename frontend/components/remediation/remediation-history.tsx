'use client';

import { History, CheckCircle, XCircle, AlertCircle, Clock, RotateCcw } from 'lucide-react';
import type { RemediationRun } from '@/types/remediation';

interface RemediationHistoryProps {
  runs: RemediationRun[];
  canRetry: boolean;
  onSelectRun: (runId: string) => void;
  onRetry: () => void;
  selectedRunId?: string;
  isRetrying?: boolean;
}

export function RemediationHistory({
  runs,
  canRetry,
  onSelectRun,
  onRetry,
  selectedRunId,
  isRetrying = false,
}: RemediationHistoryProps) {
  const attempts = [...runs].reverse();

  return (
    <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          <History className="w-4 h-4 text-primary-400" />
          <span>Remediation History ({runs.length}/3)</span>
        </div>

        {canRetry && (
          <button
            onClick={onRetry}
            disabled={isRetrying}
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-primary-600/20 hover:bg-primary-600/30 text-primary-300 border border-primary-500/30 text-xs font-medium transition-colors disabled:opacity-50"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
            <span>Try Another Fix</span>
          </button>
        )}
      </div>

      {runs.length === 0 ? (
        <p className="text-xs text-[var(--text-muted)] italic">No previous attempts.</p>
      ) : (
        <div className="space-y-2">
          {attempts.map((run, idx) => {
            const attemptNumber = runs.length - idx;
            const isResolved = run.verification_status === 'resolved';
            const isFailed =
              run.status === 'failed' ||
              run.verification_status === 'verification_failed' ||
              run.verification_status === 'still_vulnerable';
            const durationSec = run.duration_ms ? (run.duration_ms / 1000).toFixed(1) : null;
            const isSelected = run.id === selectedRunId;

            return (
              <div
                key={run.id}
                onClick={() => onSelectRun(run.id)}
                className={`p-2.5 rounded-lg border cursor-pointer transition-all flex items-center justify-between ${
                  isSelected
                    ? 'border-primary-500/60 bg-primary-500/10 shadow-sm'
                    : 'border-[var(--border-subtle)] bg-black/20 hover:bg-black/30'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <span className="font-mono text-xs font-bold text-[var(--text-primary)]">
                    #{attemptNumber}
                  </span>

                  {isResolved ? (
                    <span className="flex items-center gap-1 text-xs text-emerald-400 font-medium">
                      <CheckCircle className="w-3.5 h-3.5" />
                      Resolved
                    </span>
                  ) : isFailed ? (
                    <span className="flex items-center gap-1 text-xs text-red-400 font-medium">
                      <XCircle className="w-3.5 h-3.5" />
                      Failed
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-blue-400 font-medium">
                      <AlertCircle className="w-3.5 h-3.5" />
                      {run.status}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3 text-xs text-[var(--text-muted)] font-mono">
                  {durationSec && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {durationSec}s
                    </span>
                  )}
                  <span className="text-[10px]">
                    {new Date(run.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {runs.length >= 3 && !canRetry && (
        <div className="mt-3 p-2.5 bg-amber-500/10 border border-amber-500/20 rounded text-xs text-amber-300">
          Maximum remediation attempts (3) exhausted for this finding.
        </div>
      )}
    </div>
  );
}
