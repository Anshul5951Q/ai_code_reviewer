'use client';

import { CheckCircle2, Loader2, AlertCircle, Circle } from 'lucide-react';
import type { RemediationStatus } from '@/types/remediation';

interface RemediationProgressProps {
  status: RemediationStatus;
  error?: string | null;
}

interface StepInfo {
  key: RemediationStatus;
  label: string;
}

const STEPS: StepInfo[] = [
  { key: 'queued', label: 'Queued' },
  { key: 'generating', label: 'Generating Fix' },
  { key: 'patch_generated', label: 'Patch Generated' },
  { key: 'patch_validated', label: 'Patch Validated' },
  { key: 'verifying', label: 'Verifying' },
  { key: 'completed', label: 'Completed' },
];

const STEP_ORDER: Record<string, number> = {
  queued: 0,
  generating: 1,
  patch_generated: 2,
  patch_validated: 3,
  verifying: 4,
  completed: 5,
  failed: -1,
  cancelled: -1,
};

export function RemediationProgress({ status, error }: RemediationProgressProps) {
  const isFailed = status === 'failed';
  const currentStepIndex = STEP_ORDER[status] ?? 0;

  return (
    <div className="w-full bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between relative">
        {/* Background Connecting Line */}
        <div className="absolute left-4 right-4 top-1/2 -translate-y-1/2 h-0.5 bg-white/10 -z-0" />

        {STEPS.map((step, idx) => {
          const isPast = !isFailed && currentStepIndex > idx;
          const isCurrent = !isFailed && (currentStepIndex === idx || (idx === 5 && status === 'completed'));

          return (
            <div key={step.key} className="flex flex-col items-center relative z-10">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-all ${
                  isPast
                    ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400'
                    : isCurrent
                    ? status === 'completed'
                      ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.3)]'
                      : 'bg-blue-500/20 border-blue-500 text-blue-400 shadow-[0_0_12px_rgba(59,130,246,0.3)]'
                    : isFailed && idx === currentStepIndex
                    ? 'bg-red-500/20 border-red-500 text-red-400'
                    : 'bg-[#161b22] border-[var(--border-subtle)] text-[var(--text-muted)]'
                }`}
              >
                {isPast ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : isCurrent ? (
                  status === 'completed' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                  )
                ) : isFailed && idx === currentStepIndex ? (
                  <AlertCircle className="w-4 h-4 text-red-400" />
                ) : (
                  <Circle className="w-3 h-3 opacity-40" />
                )}
              </div>
              <span
                className={`text-[11px] mt-2 font-medium select-none ${
                  isCurrent
                    ? 'text-[var(--text-primary)] font-semibold'
                    : isPast
                    ? 'text-emerald-400'
                    : 'text-[var(--text-muted)]'
                }`}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {isFailed && error && (
        <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded text-xs text-red-400 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <span className="font-semibold">Remediation Failed:</span> {error}
          </div>
        </div>
      )}
    </div>
  );
}
