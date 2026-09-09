'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  X,
  Sparkles,
  ShieldAlert,
  ShieldCheck,
  Code2,
  FileCheck,
  CheckCircle2,
} from 'lucide-react';
import type { Finding } from '@/types/security';
import type {
  RemediationHistoryResponse,
  RemediationResultResponse,
  RemediationRun,
  VerificationResult,
} from '@/types/remediation';
import {
  remediateFinding,
  getRemediation,
  getRemediationResult,
  getRemediationVerification,
  getFindingRemediations,
} from '@/lib/api';

import { RemediationDiff } from './remediation-diff';
import { RemediationProgress } from './remediation-progress';
import { RemediationSummary } from './remediation-summary';
import { VerificationResultCard } from './verification-result';
import { VerificationEvidence } from './verification-evidence';
import { RemediationHistory } from './remediation-history';

interface RemediationPanelProps {
  finding: Finding;
  onClose: () => void;
  onStatusChange?: (newStatus: string) => void;
}

export function RemediationPanel({
  finding,
  onClose,
  onStatusChange,
}: RemediationPanelProps) {
  const [activeRun, setActiveRun] = useState<RemediationRun | null>(null);
  const [result, setResult] = useState<RemediationResultResponse | null>(null);
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [historyRuns, setHistoryRuns] = useState<RemediationRun[]>([]);
  const [canRetry, setCanRetry] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'diff' | 'strategy' | 'evidence'>('diff');
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  // Fetch full details for a completed remediation run
  const loadRunDetails = useCallback(
    async (runId: string) => {
      try {
        const [resData, verData] = await Promise.all([
          getRemediationResult(runId),
          getRemediationVerification(runId),
        ]);
        setResult(resData);
        setVerification(verData);
        if (onStatusChange && resData.verification_status === 'resolved') {
          onStatusChange('resolved');
        }
      } catch (err: unknown) {
        console.error('Failed to load remediation result:', err);
      }
    },
    [onStatusChange]
  );

  // Poll active run until completion or failure
  const startPolling = useCallback(
    (runId: string) => {
      stopPolling();
      pollIntervalRef.current = setInterval(async () => {
        try {
          const run = await getRemediation(runId);
          setActiveRun(run);

          if (run.status === 'completed') {
            stopPolling();
            await loadRunDetails(runId);
            // Refresh history
            const hist = await getFindingRemediations(finding.id);
            setHistoryRuns(hist.runs);
            setCanRetry(hist.can_retry);
          } else if (run.status === 'failed' || run.status === 'cancelled') {
            stopPolling();
            setError(run.error || 'Remediation pipeline encountered an error.');
            const hist = await getFindingRemediations(finding.id);
            setHistoryRuns(hist.runs);
            setCanRetry(hist.can_retry);
          }
        } catch (err: unknown) {
          console.error('Polling error:', err);
          stopPolling();
        }
      }, 1500);
    },
    [stopPolling, loadRunDetails, finding.id]
  );

  // Trigger a new remediation attempt
  const triggerRemediation = useCallback(async () => {
    try {
      setError(null);
      setResult(null);
      setVerification(null);
      setIsRetrying(true);

      const newRun = await remediateFinding(finding.id);
      setActiveRun(newRun);

      if (newRun.status === 'completed') {
        await loadRunDetails(newRun.id);
        const hist = await getFindingRemediations(finding.id);
        setHistoryRuns(hist.runs);
        setCanRetry(hist.can_retry);
      } else {
        startPolling(newRun.id);
      }
    } catch (err: unknown) {
      const errObj = err as { detail?: string; message?: string };
      setError(errObj?.detail || errObj?.message || 'Failed to trigger remediation');
    } finally {
      setIsRetrying(false);
    }
  }, [finding.id, loadRunDetails, startPolling]);

  // Initial load: check existing history or start remediation
  useEffect(() => {
    let isMounted = true;

    async function init() {
      try {
        const hist: RemediationHistoryResponse = await getFindingRemediations(finding.id);
        if (!isMounted) return;

        setHistoryRuns(hist.runs);
        setCanRetry(hist.can_retry);

        if (hist.runs.length > 0) {
          const latestRun = hist.runs[hist.runs.length - 1];
          setActiveRun(latestRun);

          if (latestRun.status === 'completed') {
            await loadRunDetails(latestRun.id);
          } else if (
            latestRun.status === 'queued' ||
            latestRun.status === 'generating' ||
            latestRun.status === 'patch_generated' ||
            latestRun.status === 'patch_validated' ||
            latestRun.status === 'verifying'
          ) {
            startPolling(latestRun.id);
          }
        } else {
          // No previous attempts: trigger initial remediation
          await triggerRemediation();
        }
      } catch {
        if (!isMounted) return;
        // If history call fails, try triggering remediation directly
        await triggerRemediation();
      }
    }

    init();

    return () => {
      isMounted = false;
      stopPolling();
    };
  }, [finding.id, loadRunDetails, startPolling, stopPolling, triggerRemediation]);

  // Select an attempt from history
  const handleSelectRun = async (runId: string) => {
    const selected = historyRuns.find((r) => r.id === runId);
    if (!selected) return;
    setActiveRun(selected);
    if (selected.status === 'completed') {
      await loadRunDetails(selected.id);
    } else {
      setResult(null);
      setVerification(null);
      if (
        selected.status === 'queued' ||
        selected.status === 'generating' ||
        selected.status === 'verifying'
      ) {
        startPolling(selected.id);
      }
    }
  };

  const isVerifiedResolved = activeRun?.verification_status === 'resolved';
  const isVerificationFailed =
    activeRun?.verification_status === 'verification_failed' ||
    activeRun?.verification_status === 'still_vulnerable';
  const isRunning =
    activeRun?.status === 'queued' ||
    activeRun?.status === 'generating' ||
    activeRun?.status === 'patch_generated' ||
    activeRun?.status === 'patch_validated' ||
    activeRun?.status === 'verifying';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div
        className="card w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden border border-[var(--border-default)] shadow-2xl relative bg-[#0b0f17]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary-600/20 border border-primary-500/30 flex items-center justify-center text-primary-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-[var(--text-primary)]">
                  AI Remediation & Verification Workspace
                </h3>
                {/* Section 47 Status Label */}
                {isVerifiedResolved ? (
                  <span className="text-[10px] font-mono uppercase font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3" /> Verified remediation
                  </span>
                ) : isVerificationFailed ? (
                  <span className="text-[10px] font-mono uppercase font-bold px-2 py-0.5 rounded bg-red-500/15 text-red-300 border border-red-500/30 flex items-center gap-1">
                    <ShieldAlert className="w-3 h-3" /> Unverified / potentially unsafe
                  </span>
                ) : (
                  <span className="text-[10px] font-mono uppercase font-bold px-2 py-0.5 rounded bg-blue-500/15 text-blue-300 border border-blue-500/30 flex items-center gap-1">
                    <Sparkles className="w-3 h-3" /> Proposed fix
                  </span>
                )}
              </div>
              <p className="text-xs text-[var(--text-secondary)] font-mono mt-0.5">
                {finding.file_path}
                {finding.start_line ? `:${finding.start_line}` : ''} · {finding.cwe || finding.category}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Active Run Pipeline Progress */}
          {activeRun && (
            <RemediationProgress
              status={activeRun.status}
              error={activeRun.error || error}
            />
          )}

          {/* Verification Verdict Card (Section 24) */}
          {activeRun && activeRun.status === 'completed' && result && (
            <VerificationResultCard
              findingTitle={finding.title}
              verificationStatus={result.verification_status}
              confidence={result.verification_confidence}
              reason={result.verification_reason}
              remainingRisk={result.remaining_risk}
              newFindingsCount={result.new_findings?.length ?? 0}
              canRetry={canRetry}
              onTryAnotherFix={triggerRemediation}
            />
          )}

          {/* Navigation Tabs */}
          {result && (
            <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] pb-2 text-xs">
              <button
                onClick={() => setActiveTab('diff')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all ${
                  activeTab === 'diff'
                    ? 'bg-primary-600/20 text-primary-300 border border-primary-500/30'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5'
                }`}
              >
                <Code2 className="w-3.5 h-3.5" />
                <span>Unified Diff & Patch</span>
              </button>

              <button
                onClick={() => setActiveTab('strategy')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all ${
                  activeTab === 'strategy'
                    ? 'bg-primary-600/20 text-primary-300 border border-primary-500/30'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5'
                }`}
              >
                <FileCheck className="w-3.5 h-3.5" />
                <span>Strategy & Rationale</span>
              </button>

              <button
                onClick={() => setActiveTab('evidence')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all ${
                  activeTab === 'evidence'
                    ? 'bg-primary-600/20 text-primary-300 border border-primary-500/30'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5'
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Verification Evidence ({verification?.evidence?.length ?? 0})</span>
              </button>
            </div>
          )}

          {/* Tab Content */}
          {result && activeTab === 'diff' && (
            <RemediationDiff
              diff={result.diff}
              filePath={result.files_changed?.[0] || finding.file_path || undefined}
            />
          )}

          {result && activeTab === 'strategy' && (
            <RemediationSummary result={result} />
          )}

          {result && activeTab === 'evidence' && (
            <VerificationEvidence
              evidence={verification?.evidence || []}
              newFindings={result.new_findings}
            />
          )}

          {/* Remediation Attempt History & Retry (Section 26) */}
          <RemediationHistory
            runs={historyRuns}
            canRetry={canRetry && !isRunning}
            onSelectRun={handleSelectRun}
            onRetry={triggerRemediation}
            selectedRunId={activeRun?.id}
            isRetrying={isRetrying}
          />
        </div>

        {/* Footer: Safe Dismiss / Info Notice */}
        <div className="flex items-center justify-between px-6 py-3.5 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] text-xs">
          <span className="text-[var(--text-muted)] italic">
            Fix applied and verified inside isolated workspace. No changes written to repository.
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg border border-[var(--border-subtle)] bg-white/5 hover:bg-white/10 text-[var(--text-primary)] transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
