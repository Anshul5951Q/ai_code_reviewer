'use client';

import { useState, useEffect } from 'react';
import { X, FileCode, AlertTriangle, Sparkles, ShieldCheck, ShieldAlert, Layers } from 'lucide-react';
import type { Finding, CorrelatedFinding } from '@/types/security';
import { RemediationPanel } from '@/components/remediation/remediation-panel';

interface FindingDetailModalProps {
  finding: Finding | null;
  correlatedFinding?: CorrelatedFinding | null;
  onClose: () => void;
  onStatusChange?: (findingId: string, newStatus: string) => void;
}

export function FindingDetailModal({
  finding,
  correlatedFinding,
  onClose,
  onStatusChange,
}: FindingDetailModalProps) {
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

  const activeItem = correlatedFinding ?? finding;
  if (!activeItem) return null;

  const effectiveStatus =
    statusOverride && statusOverride.id === activeItem.id ? statusOverride.status : activeItem.status;
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

  const lineRange = activeItem.start_line
    ? activeItem.end_line && activeItem.end_line !== activeItem.start_line
      ? `Lines ${activeItem.start_line}–${activeItem.end_line}`
      : `Line ${activeItem.start_line}`
    : activeItem.line_number
    ? `Line ${activeItem.line_number}`
    : 'Entire File';

  const confidencePct =
    activeItem.confidence !== null && activeItem.confidence !== undefined
      ? `${Math.round(activeItem.confidence * 100)}%`
      : '—';

  // Construct a Finding proxy if only correlatedFinding is provided for the RemediationPanel
  const remediableFinding: Finding = finding ?? {
    id: correlatedFinding?.primary_finding_id ?? activeItem.id,
    review_id: activeItem.review_id,
    category: activeItem.category,
    severity: activeItem.severity,
    title: activeItem.title,
    description: activeItem.description ?? null,
    file_path: activeItem.file_path ?? null,
    line_number: activeItem.line_number ?? null,
    start_line: activeItem.start_line ?? null,
    end_line: activeItem.end_line ?? null,
    confidence: activeItem.confidence ?? 0.85,
    evidence: activeItem.evidence ?? null,
    cwe: activeItem.cwe ?? null,
    status: activeItem.status,
    created_at: activeItem.created_at,
  };

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
                    activeItem.severity
                  )}`}
                >
                  {activeItem.severity}
                </span>

                <span className="text-xs font-medium px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[var(--text-secondary)] capitalize">
                  {activeItem.category}
                </span>

                {correlatedFinding && (
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30 flex items-center gap-1">
                    <Layers size={11} /> Unified Correlated Issue
                  </span>
                )}

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
                    <ShieldAlert size={11} /> Verification Failed
                  </span>
                ) : null}

                {activeItem.cwe && (
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    {activeItem.cwe}
                  </span>
                )}
              </div>

              <h3 className="text-base font-semibold text-[var(--text-primary)] leading-snug">
                {activeItem.title}
              </h3>
            </div>

            <button
              onClick={onClose}
              className="p-1 rounded-md text-[var(--text-tertiary)] hover:text-white hover:bg-white/10 transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Root Cause Callout (if correlated) */}
          {correlatedFinding?.root_cause && (
            <div className="mt-4 p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
              <div className="text-[11px] font-mono font-bold uppercase text-purple-400 mb-1 flex items-center gap-1.5">
                <Sparkles size={12} /> Root Cause Analysis
              </div>
              <div className="text-[12px] text-purple-200/90 leading-relaxed">
                {correlatedFinding.root_cause}
              </div>
            </div>
          )}

          {/* Correlation Logic Explanation */}
          {correlatedFinding?.correlation_explanation && (
            <div className="mt-3 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <div className="text-[11px] font-mono font-bold uppercase text-blue-400 mb-1">
                Correlation Rationale & Risk Policy
              </div>
              <div className="text-[12px] text-blue-200/90 leading-relaxed">
                {correlatedFinding.correlation_explanation}
              </div>
            </div>
          )}

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-3 py-4 border-b border-[var(--border-subtle)] text-xs">
            {activeItem.file_path && (
              <div className="flex items-center gap-2 text-[var(--text-secondary)]">
                <FileCode size={13} className="text-[var(--text-tertiary)] shrink-0" />
                <span className="font-mono text-[var(--text-primary)] truncate">
                  {activeItem.file_path}
                </span>
              </div>
            )}

            <div className="flex items-center gap-2 text-[var(--text-secondary)]">
              <span className="text-[var(--text-tertiary)]">Location:</span>
              <span className="font-mono text-[var(--text-primary)]">{lineRange}</span>
            </div>

            <div className="flex items-center gap-2 text-[var(--text-secondary)]">
              <span className="text-[var(--text-tertiary)]">Confidence:</span>
              <span className="font-mono text-emerald-400">{confidencePct}</span>
            </div>

            {finding?.source && (
              <div className="flex items-center gap-2 text-[var(--text-secondary)]">
                <span className="text-[var(--text-tertiary)]">Detected by:</span>
                <span className="font-medium text-purple-400 capitalize">
                  {finding.source.replace(/_/g, ' ')}
                </span>
              </div>
            )}
          </div>

          {/* Constituent Source Findings (Traceability) */}
          {correlatedFinding && correlatedFinding.relationships && correlatedFinding.relationships.length > 0 && (
            <div className="py-4 border-b border-[var(--border-subtle)]">
              <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-2.5 flex items-center justify-between">
                <span>Constituent Source Findings ({correlatedFinding.relationships.length})</span>
                <span className="text-[10px] text-emerald-400 font-mono">100% Traceable</span>
              </h4>
              <div className="space-y-2">
                {correlatedFinding.relationships.map((rel, idx) => (
                  <div
                    key={rel.id ?? idx}
                    className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-mono font-bold uppercase text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                        {rel.relationship_type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-[var(--text-tertiary)] font-mono">
                        Confidence {Math.round(rel.confidence * 100)}%
                      </span>
                    </div>

                    {rel.rationale && (
                      <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed">
                        {rel.rationale}
                      </p>
                    )}

                    {rel.source_finding && (
                      <div className="pt-1 text-[11px] text-[var(--text-tertiary)] font-mono flex flex-wrap items-center gap-2 border-t border-white/5">
                        <span className="text-purple-300 font-semibold">
                          via {rel.source_finding.source?.replace(/_/g, ' ')}
                        </span>
                        <span>•</span>
                        <span className="uppercase text-amber-300 font-semibold">
                          {rel.source_finding.severity}
                        </span>
                        {rel.source_finding.file_path && (
                          <>
                            <span>•</span>
                            <span className="truncate">{rel.source_finding.file_path}:{rel.source_finding.start_line}</span>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Description */}
          <div className="py-4 border-b border-[var(--border-subtle)]">
            <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
              Consolidated Description
            </h4>
            <p className="text-[13px] leading-relaxed text-[var(--text-secondary)] whitespace-pre-wrap">
              {activeItem.description ?? 'No detailed description provided.'}
            </p>
          </div>

          {/* Evidence */}
          {activeItem.evidence && (
            <div className="py-4 border-b border-[var(--border-subtle)]">
              <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
                Evidence & Code Snippet
              </h4>
              <div className="p-3 rounded-md bg-black/50 border border-white/10 font-mono text-[11px] text-emerald-300/90 overflow-x-auto whitespace-pre-wrap leading-normal">
                {activeItem.evidence}
              </div>
            </div>
          )}

          {/* Why it matters */}
          <div className="py-4 border-b border-[var(--border-subtle)]">
            <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <AlertTriangle size={13} className="text-amber-400" />
              Impact & Engineering Context
            </h4>
            <p className="text-[12px] leading-relaxed text-[var(--text-secondary)]">
              {activeItem.category === 'security'
                ? 'Security vulnerabilities can lead to data exposure, unauthorized manipulation, or remote execution. Remediating input validation and boundary checks is essential before deployment.'
                : 'Quality and maintainability issues increase technical debt, defect rates, and operational complexity over time. Refactoring keeps codebase resilient.'}
            </p>
          </div>

          {/* Actions Bar */}
          <div className="mt-4 pt-3 flex items-center justify-between">
            <span className="text-[11px] text-[var(--text-tertiary)] font-mono">
              ID: {activeItem.id.slice(0, 8)}…
            </span>

            <div className="flex items-center gap-2.5">
              <button
                onClick={() => setShowRemediation(true)}
                className={`text-xs px-4 py-2 rounded-lg font-medium transition-all shadow-sm flex items-center gap-1.5 ${
                  isResolved
                    ? 'bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40'
                    : 'bg-indigo-600 hover:bg-indigo-500 text-white'
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
          finding={remediableFinding}
          onClose={() => setShowRemediation(false)}
          onStatusChange={(newStatus) => {
            setStatusOverride({ id: activeItem.id, status: newStatus });
            if (onStatusChange) onStatusChange(activeItem.id, newStatus);
          }}
        />
      )}
    </>
  );
}
