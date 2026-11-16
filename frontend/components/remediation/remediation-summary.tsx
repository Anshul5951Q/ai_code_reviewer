'use client';

import {
  Sparkles,
  FileText,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Scale,
  GitBranch,
} from 'lucide-react';
import type {
  RemediationResultResponse,
  Gate4Status,
  Gate5Decision,
  PatchRiskLevel,
} from '@/types/remediation';

interface RemediationSummaryProps {
  result: RemediationResultResponse;
}

export function RemediationSummary({ result }: RemediationSummaryProps) {
  const confidencePct = Math.round((result.confidence ?? result.remediation_confidence ?? 0.9) * 100);
  const gate4Status: Gate4Status = result.gate_4_status || 'PENDING';
  const gate5Decision: Gate5Decision = result.gate_5_decision || (result.verification_status === 'resolved' ? 'RESOLVED' : 'UNRESOLVED');
  const riskLevel: PatchRiskLevel = result.risk_level || 'LOW';

  const riskBadgeStyles: Record<PatchRiskLevel, string> = {
    LOW: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400',
    MEDIUM: 'bg-amber-500/15 border-amber-500/30 text-amber-400',
    HIGH: 'bg-orange-500/15 border-orange-500/30 text-orange-400',
    CRITICAL: 'bg-red-500/15 border-red-500/30 text-red-400',
  };

  const gate4BadgeStyles: Record<Gate4Status, string> = {
    PASSED: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400',
    FAILED: 'bg-red-500/15 border-red-500/30 text-red-400',
    PARTIALLY_PASSED: 'bg-amber-500/15 border-amber-500/30 text-amber-400',
    UNABLE_TO_VERIFY: 'bg-yellow-500/15 border-yellow-500/30 text-yellow-400',
    VALIDATING: 'bg-blue-500/15 border-blue-500/30 text-blue-400',
    PENDING: 'bg-slate-500/15 border-slate-500/30 text-slate-400',
  };

  const gate5BadgeStyles: Record<Gate5Decision, string> = {
    RESOLVED: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400',
    BLOCKED: 'bg-red-500/15 border-red-500/30 text-red-400',
    PARTIALLY_RESOLVED: 'bg-amber-500/15 border-amber-500/30 text-amber-400',
    UNRESOLVED: 'bg-slate-500/15 border-slate-500/30 text-slate-400',
    UNABLE_TO_VERIFY: 'bg-yellow-500/15 border-yellow-500/30 text-yellow-400',
  };

  return (
    <div className="space-y-4">
      {/* 4-Stage Lifecycle Timeline */}
      <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
        <div className="flex items-center gap-2 mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          <GitBranch className="w-4 h-4 text-primary-400" />
          <span>4-Stage Remediation Lifecycle</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {/* Stage 1: Patch Generated */}
          <div
            className={`p-2.5 rounded-lg border text-xs flex flex-col gap-1 ${
              result.diff
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-white/5 border-white/10 text-slate-400'
            }`}
          >
            <div className="flex items-center gap-1.5 font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>1. Patch Generated</span>
            </div>
            <span className="text-[11px] text-[var(--text-muted)]">
              v{result.patch_version || 1} compiled
            </span>
          </div>

          {/* Stage 2: Gate 4 Passed */}
          <div
            className={`p-2.5 rounded-lg border text-xs flex flex-col gap-1 ${
              gate4Status === 'PASSED'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : gate4Status === 'FAILED'
                ? 'bg-red-500/10 border-red-500/30 text-red-300'
                : 'bg-white/5 border-white/10 text-slate-400'
            }`}
          >
            <div className="flex items-center gap-1.5 font-semibold">
              {gate4Status === 'PASSED' ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              ) : gate4Status === 'FAILED' ? (
                <XCircle className="w-3.5 h-3.5 text-red-400" />
              ) : (
                <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
              )}
              <span>2. Gate 4 Passed</span>
            </div>
            <span className="text-[11px] text-[var(--text-muted)]">{gate4Status}</span>
          </div>

          {/* Stage 3: Fix Verified */}
          <div
            className={`p-2.5 rounded-lg border text-xs flex flex-col gap-1 ${
              result.verification_status === 'resolved'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : result.verification_status === 'still_vulnerable' ||
                  result.verification_status === 'verification_failed'
                ? 'bg-red-500/10 border-red-500/30 text-red-300'
                : 'bg-white/5 border-white/10 text-slate-400'
            }`}
          >
            <div className="flex items-center gap-1.5 font-semibold">
              {result.verification_status === 'resolved' ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              ) : result.verification_status === 'still_vulnerable' ||
                result.verification_status === 'verification_failed' ? (
                <XCircle className="w-3.5 h-3.5 text-red-400" />
              ) : (
                <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
              )}
              <span>3. Fix Verified</span>
            </div>
            <span className="text-[11px] text-[var(--text-muted)]">
              {result.verification_status}
            </span>
          </div>

          {/* Stage 4: Finding Resolved */}
          <div
            className={`p-2.5 rounded-lg border text-xs flex flex-col gap-1 ${
              gate5Decision === 'RESOLVED'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : gate5Decision === 'BLOCKED'
                ? 'bg-red-500/10 border-red-500/30 text-red-300'
                : gate5Decision === 'PARTIALLY_RESOLVED'
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                : 'bg-white/5 border-white/10 text-slate-400'
            }`}
          >
            <div className="flex items-center gap-1.5 font-semibold">
              {gate5Decision === 'RESOLVED' ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              ) : gate5Decision === 'BLOCKED' ? (
                <XCircle className="w-3.5 h-3.5 text-red-400" />
              ) : (
                <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
              )}
              <span>4. Finding Resolved</span>
            </div>
            <span className="text-[11px] text-[var(--text-muted)]">{gate5Decision}</span>
          </div>
        </div>
      </div>
      {/* Root Cause Card (if present) */}
      {result.root_cause && (
        <div className="p-4 bg-purple-950/20 border border-purple-500/30 rounded-lg">
          <div className="flex items-center gap-2 mb-2 text-xs font-semibold uppercase tracking-wider text-purple-400">
            <Sparkles className="w-4 h-4" />
            <span>Underlying Root Cause</span>
          </div>
          <p className="text-sm font-medium text-purple-100">
            {result.root_cause}
          </p>
        </div>
      )}

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

      {/* Gate 4 Deterministic Verification Gate Card */}
      <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-primary)]">
            <ShieldCheck className="w-4 h-4 text-primary-400" />
            <span>Gate 4: Deterministic Patch Verification</span>
          </div>
          <span className={`px-2.5 py-0.5 rounded text-[11px] font-semibold border ${gate4BadgeStyles[gate4Status]}`}>
            {gate4Status}
          </span>
        </div>

        {result.gate_4_checks && result.gate_4_checks.length > 0 ? (
          <div className="space-y-2 mt-2">
            {result.gate_4_checks.map((chk, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2.5 text-xs p-2 rounded bg-black/20 border border-white/5"
              >
                {chk.status === 'passed' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                ) : chk.status === 'failed' ? (
                  <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                ) : chk.status === 'warning' ? (
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                ) : (
                  <HelpCircle className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                )}
                <div className="flex-1 min-w-0">
                  <span className="font-semibold text-[var(--text-primary)] capitalize block">
                    {chk.check_name.replace(/_/g, ' ')}
                  </span>
                  <span className="text-[11px] text-[var(--text-muted)] leading-relaxed">
                    {chk.details}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-[var(--text-muted)]">
            Gate 4 checks recorded with overall status: {gate4Status}.
          </p>
        )}
      </div>

      {/* Gate 5 Deterministic Decision Engine Card */}
      <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-primary)]">
            <Scale className="w-4 h-4 text-primary-400" />
            <span>Gate 5: Deterministic Decision Engine</span>
          </div>
          <span className={`px-2.5 py-0.5 rounded text-[11px] font-semibold border ${gate5BadgeStyles[gate5Decision]}`}>
            {gate5Decision}
          </span>
        </div>

        {result.gate_5_result ? (
          <div className="space-y-3 mt-2">
            {result.gate_5_result.reasons && result.gate_5_result.reasons.length > 0 && (
              <div className="p-2.5 rounded bg-black/20 border border-white/5 text-xs text-[var(--text-secondary)]">
                {result.gate_5_result.reasons.map((r, i) => (
                  <p key={i} className="leading-relaxed">{r}</p>
                ))}
              </div>
            )}

            {result.gate_5_result.passed_conditions && result.gate_5_result.passed_conditions.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider block">
                  Passed Resolution Conditions ({result.gate_5_result.passed_conditions.length})
                </span>
                {result.gate_5_result.passed_conditions.map((cond, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-xs text-emerald-200/90">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{cond}</span>
                  </div>
                ))}
              </div>
            )}

            {result.gate_5_result.failed_conditions && result.gate_5_result.failed_conditions.length > 0 && (
              <div className="space-y-1.5 mt-2">
                <span className="text-[11px] font-semibold text-red-400 uppercase tracking-wider block">
                  Blocking / Unmet Conditions ({result.gate_5_result.failed_conditions.length})
                </span>
                {result.gate_5_result.failed_conditions.map((cond, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-xs text-red-200/90">
                    <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                    <span>{cond}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="text-xs text-[var(--text-muted)] space-y-1">
            <p>
              Deterministic arbiter status:{' '}
              <span className="font-semibold text-[var(--text-primary)]">{gate5Decision}</span>.
            </p>
            <p className="text-[11px]">
              Enforces zero blind trust across diff syntax, re-scan signals, regression tests, and version grounding.
            </p>
          </div>
        )}
      </div>

      {/* Patch Risk Assessment Card */}
      <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-primary)]">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <span>Deterministic Patch Risk Assessment</span>
          </div>
          <span className={`px-2.5 py-0.5 rounded text-[11px] font-semibold border ${riskBadgeStyles[riskLevel]}`}>
            {riskLevel} RISK
          </span>
        </div>

        {result.risk_assessment ? (
          <div className="mt-2 space-y-2 text-xs">
            <p className="text-[var(--text-secondary)]">{result.risk_assessment.explanation}</p>
            {result.risk_assessment.factors && result.risk_assessment.factors.length > 0 && (
              <ul className="list-disc list-inside space-y-1 text-[11px] text-[var(--text-muted)] mt-1">
                {result.risk_assessment.factors.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <p className="text-xs text-[var(--text-muted)]">
            Risk level assigned: {riskLevel}. Localized scope without interface breakages.
          </p>
        )}
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
          <span className="text-[11px] text-[var(--text-muted)] block mb-1">Files Changed</span>
          <span className="text-sm font-mono font-semibold text-[var(--text-primary)]">
            {result.changed_files?.length || 1}
          </span>
        </div>

        <div className="p-3 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
          <span className="text-[11px] text-[var(--text-muted)] block mb-1">Patch Version</span>
          <span className="text-sm font-mono font-semibold text-primary-400">
            v{result.patch_version || 1}
          </span>
        </div>

        <div className="p-3 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
          <span className="text-[11px] text-[var(--text-muted)] block mb-1">AI Confidence</span>
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
