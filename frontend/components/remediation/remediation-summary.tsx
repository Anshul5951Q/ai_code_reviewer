'use client';

import { Sparkles, FileText } from 'lucide-react';
import type { RemediationResultResponse } from '@/types/remediation';

interface RemediationSummaryProps {
  result: RemediationResultResponse;
}

export function RemediationSummary({ result }: RemediationSummaryProps) {
  const confidencePct = Math.round((result.remediation_confidence ?? 0.9) * 100);

  return (
    <div className="space-y-4">
      {/* Strategy Card */}
      <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
        <div className="flex items-center gap-2 mb-2 text-xs font-semibold uppercase tracking-wider text-primary-400">
          <Sparkles className="w-4 h-4" />
          <span>Remediation Strategy</span>
        </div>
        <p className="text-sm font-medium text-[var(--text-primary)]">
          {result.strategy}
        </p>
      </div>

      {/* Technical Explanation Card */}
      <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
        <div className="flex items-center gap-2 mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          <FileText className="w-4 h-4 text-slate-400" />
          <span>Why This Fix Works</span>
        </div>
        <p className="text-xs leading-relaxed text-[var(--text-secondary)] whitespace-pre-wrap">
          {result.explanation}
        </p>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="p-3 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
          <span className="text-[11px] text-[var(--text-muted)] block mb-1">Files Changed</span>
          <span className="text-sm font-mono font-semibold text-[var(--text-primary)]">
            {result.files_changed?.length ?? 1}
          </span>
        </div>

        <div className="p-3 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
          <span className="text-[11px] text-[var(--text-muted)] block mb-1">AI Fix Confidence</span>
          <div className="flex items-center gap-2">
            <span className="text-sm font-mono font-semibold text-emerald-400">
              {confidencePct}%
            </span>
            <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full"
                style={{ width: `${confidencePct}%` }}
              />
            </div>
          </div>
        </div>

        <div className="p-3 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
          <span className="text-[11px] text-[var(--text-muted)] block mb-1">Attempt</span>
          <span className="text-sm font-mono font-semibold text-[var(--text-primary)]">
            #{result.attempt_number ?? 1}
          </span>
        </div>
      </div>
    </div>
  );
}
