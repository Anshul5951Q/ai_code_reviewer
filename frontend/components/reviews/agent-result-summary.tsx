'use client';

import { Shield, Sparkles, Layers, Activity, FileCheck, AlertTriangle } from 'lucide-react';
import type { Review } from '@/types/review';
import type { RepositorySnapshot } from '@/types/analysis';

interface AgentResultSummaryProps {
  review: Review;
  totalFindings: number;
  snapshot?: RepositorySnapshot | null;
}

export function AgentResultSummary({ review, totalFindings, snapshot }: AgentResultSummaryProps) {
  const coverage = snapshot?.structure?.coverage;
  const coveragePct = coverage ? Math.round(coverage.coverage_percentage) : null;
  const coverageStatus = coverage?.coverage_status || (review.overall_score === 0 ? 'INSUFFICIENT ANALYSIS COVERAGE' : 'ADEQUATE ANALYSIS COVERAGE');
  const isInsufficient = coveragePct === 0 || coverageStatus === 'INSUFFICIENT ANALYSIS COVERAGE';

  const getScoreColor = (score: number | null | undefined) => {
    if (score === null || score === undefined) return 'text-[var(--text-tertiary)]';
    if (isInsufficient) return 'text-amber-400';
    if (score >= 80) return 'text-emerald-400';
    if (score >= 60) return 'text-amber-400';
    return 'text-red-400';
  };

  const getScoreBg = (score: number | null | undefined) => {
    if (score === null || score === undefined) return 'bg-white/5 border-white/10';
    if (isInsufficient) return 'bg-amber-500/10 border-amber-500/20';
    if (score >= 80) return 'bg-emerald-500/10 border-emerald-500/20';
    if (score >= 60) return 'bg-amber-500/10 border-amber-500/20';
    return 'bg-red-500/10 border-red-500/20';
  };

  return (
    <div className="card p-5 mb-6 border border-[var(--border-default)]">
      {/* Insufficient Coverage Warning Banner */}
      {isInsufficient && (
        <div className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-start gap-3">
          <AlertTriangle size={18} className="text-amber-400 shrink-0 mt-0.5" />
          <div className="text-[12px] text-amber-200">
            <span className="font-semibold block text-[13px] text-amber-300">
              INSUFFICIENT ANALYSIS COVERAGE (0 Files Analyzed)
            </span>
            Source code could not be inspected due to rate limits or file retrieval errors. A score of 0% is assigned to avoid false assurance of security.
          </div>
        </div>
      )}

      {/* No Vulnerabilities Detected in Analyzed Scope Banner */}
      {!isInsufficient && totalFindings === 0 && review.status === 'completed' && (
        <div className="mb-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-start gap-3">
          <FileCheck size={18} className="text-emerald-400 shrink-0 mt-0.5" />
          <div className="text-[12px] text-emerald-200">
            <span className="font-semibold block text-[13px] text-emerald-300">
              NO VULNERABILITIES DETECTED IN ANALYZED SCOPE
            </span>
            All {coverage?.analyzed_count ?? snapshot?.source_files ?? 'eligible'} analyzed source files verified clean against standard security and maintainability rules.
          </div>
        </div>
      )}

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-[15px] font-semibold" style={{ color: 'var(--text-primary)' }}>
              Analysis Results & Deterministic Scores
            </h3>
            <span
              className={`text-[11px] font-mono px-2 py-0.5 rounded-full capitalize ${
                review.status === 'completed' && !isInsufficient
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'bg-amber-500/10 text-amber-400'
              }`}
            >
              {isInsufficient ? 'Coverage Degraded' : review.status.replace(/_/g, ' ')}
            </span>
          </div>
          <p className="text-[12px]" style={{ color: 'var(--text-tertiary)' }}>
            Calculated deterministically from normalized findings and severity-weighted penalties.
          </p>
        </div>

        <div className="flex items-center gap-6">
          {coverage && (
            <div className="text-right">
              <span className="text-[11px] text-[var(--text-tertiary)]">Analysis Coverage</span>
              <p className="text-[16px] font-mono font-bold text-purple-400">
                {coveragePct}% ({coverage.analyzed_count}/{coverage.total_eligible_source} files)
              </p>
            </div>
          )}
          <div className="text-right">
            <span className="text-[11px] text-[var(--text-tertiary)]">Total Findings</span>
            <p className="text-[18px] font-mono font-bold" style={{ color: 'var(--text-primary)' }}>
              {totalFindings}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 pt-4">
        {/* Overall Score */}
        <div className={`p-3 rounded-lg border flex items-center gap-3 ${getScoreBg(review.overall_score)}`}>
          <div className="p-2 rounded bg-black/20">
            <Activity size={20} className={getScoreColor(review.overall_score)} />
          </div>
          <div>
            <span className="text-[11px] text-[var(--text-tertiary)]">Overall Health</span>
            <div className={`text-[18px] font-mono font-bold ${getScoreColor(review.overall_score)}`}>
              {review.overall_score !== null ? `${Math.round(review.overall_score)}%` : '—'}
            </div>
          </div>
        </div>

        {/* Security Score */}
        <div className={`p-3 rounded-lg border flex items-center gap-3 ${getScoreBg(review.security_score)}`}>
          <div className="p-2 rounded bg-black/20">
            <Shield size={20} className={getScoreColor(review.security_score)} />
          </div>
          <div>
            <span className="text-[11px] text-[var(--text-tertiary)]">Security Posture</span>
            <div className={`text-[18px] font-mono font-bold ${getScoreColor(review.security_score)}`}>
              {review.security_score !== null ? `${Math.round(review.security_score)}%` : '—'}
            </div>
          </div>
        </div>

        {/* Quality Score */}
        <div className={`p-3 rounded-lg border flex items-center gap-3 ${getScoreBg(review.quality_score)}`}>
          <div className="p-2 rounded bg-black/20">
            <Sparkles size={20} className={getScoreColor(review.quality_score)} />
          </div>
          <div>
            <span className="text-[11px] text-[var(--text-tertiary)]">Code Quality</span>
            <div className={`text-[18px] font-mono font-bold ${getScoreColor(review.quality_score)}`}>
              {review.quality_score !== null ? `${Math.round(review.quality_score)}%` : '—'}
            </div>
          </div>
        </div>

        {/* Architecture Score */}
        <div className={`p-3 rounded-lg border flex items-center gap-3 ${getScoreBg(review.architecture_score)}`}>
          <div className="p-2 rounded bg-black/20">
            <Layers size={20} className={getScoreColor(review.architecture_score)} />
          </div>
          <div>
            <span className="text-[11px] text-[var(--text-tertiary)]">Architecture</span>
            <div className={`text-[18px] font-mono font-bold ${getScoreColor(review.architecture_score)}`}>
              {review.architecture_score !== null && review.architecture_score !== undefined
                ? `${Math.round(review.architecture_score)}%`
                : '—'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
