'use client';

import { useState, useEffect } from 'react';
import { X, FileCode, AlertTriangle, ExternalLink, Sparkles, ShieldCheck, ShieldAlert } from 'lucide-react';
import type { Finding } from '@/types/security';
import { RemediationPanel } from '@/components/remediation/remediation-panel';

interface FindingDetailModalProps {
  finding: Finding | null;
  onClose: () => void;
  onStatusChange?: (findingId: string, newStatus: string) => void;
}

export function FindingDetailModal({ finding, onClose, onStatusChange }: FindingDetailModalProps) {
  const [showRemediation, setShowRemediation] = useState(false);
  const [statusOverride, setStatusOverride] = useState<{ id: string; status: string } | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showRemediation) {
          setShowRemediation(false);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, showRemediation]);

  if (!finding) return null;

  const effectiveStatus =
    statusOverride && statusOverride.id === finding.id ? statusOverride.status : finding.status;
  const isResolved = effectiveStatus === 'resolved';
  const isInProgress = effectiveStatus === 'remediation_in_progress';
  const isFailed = effectiveStatus === 'verification_failed';

  const getSeverityBadgeClass = (sev: string) => {
    switch (sev) {
      case 'critical':
        return 'bg-red-500/15 text-red-400 border-red-500/30';
      case 'high':
        return 'bg-orange-500/15 text-orange-400 border-orange-500/30';
      case 'medium':
        return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
      case 'low':
        return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
      default:
        return 'bg-slate-500/15 text-slate-400 border-slate-500/30';
    }
  };

  const lineRange = finding.start_line
    ? finding.end_line && finding.end_line !== finding.start_line
      ? `Lines ${finding.start_line}–${finding.end_line}`
      : `Line ${finding.start_line}`
    : finding.line_number
    ? `Line ${finding.line_number}`
    : 'Entire File';

  const confidencePct = finding.confidence !== null && finding.confidence !== undefined
    ? `${Math.round(finding.confidence * 100)}%`
    : '—';

  return (
    <>
      <div className="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
        <div
          className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 border border-[var(--border-default)] shadow-2xl relative bg-[#0d1117]"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span
                  className={`text-xs font-mono font-bold uppercase px-2.5 py-0.5 rounded border ${getSeverityBadgeClass(
                    finding.severity
                  )}`}
                >
                  {finding.severity}
                </span>

                <span className="text-xs font-medium px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[var(--text-secondary)] capitalize">
                  {finding.category}
                </span>

                {/* Remediation Status Pill */}
                {isResolved ? (
                  <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center gap-1">
                    <ShieldCheck size={11} /> Resolved
                  </span>
                ) : isInProgress ? (
                  <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-blue-500/15 border border-blue-500/30 text-blue-400 flex items-center gap-1">
                    <Sparkles size={11} className="animate-spin" /> Remediation in progress
                  </span>
                ) : isFailed ? (
                  <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-red-500/15 border border-red-500/30 text-red-400 flex items-center gap-1">
                    <ShieldAlert size={11} /> Verification failed
                  </span>
                ) : null}

                {finding.cwe && (
                  <a
                    href={`https://cwe.mitre.org/data/definitions/${finding.cwe.replace(/[^0-9]/g, '')}.html`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-mono px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/30 text-blue-400 hover:bg-blue-500/20 flex items-center gap-1 transition-colors"
                  >
                    {finding.cwe}
                    <ExternalLink size={10} />
                  </a>
                )}

                <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  Confidence {confidencePct}
                </span>
              </div>

              <h2 className="text-[17px] font-bold text-[var(--text-primary)]">
                {finding.title}
              </h2>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {/* Location & Metadata */}
          <div className="py-4 border-b border-[var(--border-subtle)] grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="flex items-center gap-2 text-[var(--text-secondary)]">
              <FileCode size={14} className="text-[var(--text-tertiary)] shrink-0" />
              <span className="font-mono text-[var(--text-primary)] truncate">
                {finding.file_path ?? 'Repository-level'}
              </span>
            </div>

            <div className="flex items-center gap-2 text-[var(--text-secondary)]">
              <span className="text-[var(--text-tertiary)]">Location:</span>
              <span className="font-mono text-[var(--text-primary)]">{lineRange}</span>
            </div>

            <div className="flex items-center gap-2 text-[var(--text-secondary)]">
              <span className="text-[var(--text-tertiary)]">Detected by:</span>
              <span className="font-medium text-purple-400 capitalize">
                {(finding.source ?? 'analysis_agent').replace(/_/g, ' ')}
              </span>
            </div>

            {finding.type && (
              <div className="flex items-center gap-2 text-[var(--text-secondary)]">
                <span className="text-[var(--text-tertiary)]">Issue Type:</span>
                <span className="font-mono text-[var(--text-primary)]">{finding.type}</span>
              </div>
            )}
          </div>

          {/* Description */}
          <div className="py-4 border-b border-[var(--border-subtle)]">
            <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Description
            </h4>
            <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">
              {finding.description ?? 'No detailed description provided.'}
            </p>
          </div>

          {/* Evidence */}
          {finding.evidence && (
            <div className="py-4 border-b border-[var(--border-subtle)]">
              <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
                Evidence & Code Snippet
              </h4>
              <div className="p-3 rounded-md bg-black/50 border border-white/10 font-mono text-[11px] text-emerald-300/90 overflow-x-auto whitespace-pre-wrap leading-normal">
                {finding.evidence}
              </div>
            </div>
          )}

          {/* Why it matters */}
          <div className="py-4 border-b border-[var(--border-subtle)]">
            <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <AlertTriangle size={13} className="text-amber-400" />
              Why This Matters
            </h4>
            <p className="text-[12px] leading-relaxed text-[var(--text-secondary)]">
              {finding.category === 'security'
                ? 'Security vulnerabilities can lead to data exposure, unauthorized manipulation, or remote execution. Remediating input validation and boundary checks is essential before deployment.'
                : 'Quality and maintainability issues increase technical debt, defect rates, and operational complexity over time. Refactoring keeps codebase resilient.'}
            </p>
          </div>

          {/* Actions Bar */}
          <div className="mt-4 pt-3 flex items-center justify-between">
            <span className="text-[11px] text-[var(--text-tertiary)] font-mono">
              ID: {finding.id.slice(0, 8)}…
            </span>

            <div className="flex items-center gap-2.5">
              <button
                onClick={() => setShowRemediation(true)}
                className={`text-xs px-4 py-2 rounded-lg font-medium transition-all shadow-sm flex items-center gap-1.5 ${
                  isResolved
                    ? 'bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40'
                    : 'bg-primary-600 hover:bg-primary-500 text-white'
                }`}
              >
                <Sparkles size={13} />
                <span>{isResolved ? 'View Verified Fix' : 'Fix with AI'}</span>
              </button>

              <button onClick={onClose} className="btn btn-ghost text-xs px-4 py-2">
                Close
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Embedded Remediation & Verification Panel */}
      {showRemediation && (
        <RemediationPanel
          finding={finding}
          onClose={() => setShowRemediation(false)}
          onStatusChange={(newStatus) => {
            setStatusOverride({ id: finding.id, status: newStatus });
            if (onStatusChange) onStatusChange(finding.id, newStatus);
          }}
        />
      )}
    </>
  );
}

