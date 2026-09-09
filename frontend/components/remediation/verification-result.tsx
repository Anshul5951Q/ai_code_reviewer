'use client';

import { CheckCircle2, AlertTriangle, XCircle, ShieldCheck, ShieldAlert, Cpu } from 'lucide-react';
import type { VerificationStatus } from '@/types/remediation';

interface VerificationResultProps {
  findingTitle: string;
  verificationStatus: VerificationStatus;
  confidence: number;
  reason: string;
  remainingRisk?: string | null;
  newFindingsCount?: number;
  onTryAnotherFix?: () => void;
  canRetry?: boolean;
}

export function VerificationResultCard({
  findingTitle,
  verificationStatus,
  confidence,
  reason,
  remainingRisk,
  newFindingsCount = 0,
  onTryAnotherFix,
  canRetry = false,
}: VerificationResultProps) {
  const isResolved = verificationStatus === 'resolved';
  const isPartial = verificationStatus === 'partially_resolved';
  const confidencePct = Math.round((confidence ?? 0.95) * 100);

  if (isResolved) {
    return (
      <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-5 shadow-lg relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-2xl -mr-10 -mt-10" />

        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
            <CheckCircle2 className="w-5 h-5" />
            <span>Vulnerability Resolved</span>
          </div>
          <span className="text-xs font-mono font-bold px-2.5 py-1 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            Confidence {confidencePct}%
          </span>
        </div>

        <div className="mt-3">
          <h4 className="text-base font-semibold text-[var(--text-primary)]">
            {findingTitle}
          </h4>
          <p className="mt-2 text-xs leading-relaxed text-slate-300">
            {reason}
          </p>
        </div>

        {/* Verification Checkpoints */}
        <div className="mt-4 pt-4 border-t border-emerald-500/20 grid grid-cols-3 gap-2 text-xs">
          <div className="flex items-center gap-1.5 text-emerald-300">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Static analysis ✓</span>
          </div>
          <div className="flex items-center gap-1.5 text-emerald-300">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <span>AI verification ✓</span>
          </div>
          <div className="flex items-center gap-1.5 text-emerald-300">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>New issues {newFindingsCount}</span>
          </div>
        </div>
      </div>
    );
  }

  // Failed, Partial, or Still Vulnerable
  return (
    <div
      className={`rounded-xl border p-5 shadow-lg relative overflow-hidden ${
        isPartial
          ? 'border-amber-500/30 bg-amber-950/20'
          : 'border-red-500/30 bg-red-950/20'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div
          className={`flex items-center gap-2 font-bold text-sm ${
            isPartial ? 'text-amber-400' : 'text-red-400'
          }`}
        >
          {isPartial ? (
            <AlertTriangle className="w-5 h-5" />
          ) : (
            <XCircle className="w-5 h-5" />
          )}
          <span>
            {isPartial ? 'Partially Resolved' : 'Verification Failed'}
          </span>
        </div>
        <span
          className={`text-xs font-mono font-bold px-2.5 py-1 rounded border ${
            isPartial
              ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
              : 'bg-red-500/15 text-red-300 border-red-500/30'
          }`}
        >
          Confidence {confidencePct}%
        </span>
      </div>

      <div className="mt-3">
        <h4 className="text-base font-semibold text-[var(--text-primary)]">
          {findingTitle}
        </h4>
        <p className="mt-2 text-xs leading-relaxed text-slate-300">
          {reason || 'The original vulnerability may still be exploitable.'}
        </p>

        {remainingRisk && (
          <div className="mt-3 p-3 bg-red-950/40 border border-red-500/30 rounded text-xs text-red-300">
            <span className="font-semibold block mb-1">Remaining Risk:</span>
            {remainingRisk}
          </div>
        )}

        {newFindingsCount > 0 && (
          <div className="mt-2 p-2.5 bg-amber-950/40 border border-amber-500/30 rounded text-xs text-amber-300 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 flex-shrink-0" />
            <span>Warning: Patch introduces {newFindingsCount} new issue(s).</span>
          </div>
        )}
      </div>

      {canRetry && onTryAnotherFix && (
        <div className="mt-4 pt-4 border-t border-white/10 flex justify-end">
          <button
            onClick={onTryAnotherFix}
            className="px-4 py-1.5 rounded-lg bg-primary-600 hover:bg-primary-500 text-white text-xs font-medium transition-colors shadow-sm"
          >
            Try Another Fix
          </button>
        </div>
      )}
    </div>
  );
}
