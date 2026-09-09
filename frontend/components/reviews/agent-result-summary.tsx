'use client';

import { Shield, Sparkles, Layers, Activity } from 'lucide-react';
import type { Review } from '@/types/review';

interface AgentResultSummaryProps {
  review: Review;
  totalFindings: number;
}

export function AgentResultSummary({ review, totalFindings }: AgentResultSummaryProps) {
  const getScoreColor = (score: number | null | undefined) => {
    if (score === null || score === undefined) return 'text-[var(--text-tertiary)]';
    if (score >= 80) return 'text-emerald-400';
    if (score >= 60) return 'text-amber-400';
    return 'text-red-400';
  };

  const getScoreBg = (score: number | null | undefined) => {
    if (score === null || score === undefined) return 'bg-white/5 border-white/10';
    if (score >= 80) return 'bg-emerald-500/10 border-emerald-500/20';
    if (score >= 60) return 'bg-amber-500/10 border-amber-500/20';
    return 'bg-red-500/10 border-red-500/20';
  };

  return (
    <div className="card p-5 mb-6 border border-[var(--border-default)]">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-[15px] font-semibold" style={{ color: 'var(--text-primary)' }}>
              Analysis Results & Deterministic Scores
            </h3>
            <span
              className={`text-[11px] font-mono px-2 py-0.5 rounded-full capitalize ${
                review.status === 'completed'
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : review.status === 'completed_with_warnings'
                  ? 'bg-amber-500/10 text-amber-400'
                  : 'bg-red-500/10 text-red-400'
              }`}
            >
              {review.status.replace(/_/g, ' ')}
            </span>
          </div>
          <p className="text-[12px]" style={{ color: 'var(--text-tertiary)' }}>
            Calculated deterministically from normalized findings and severity-weighted penalties.
          </p>
        </div>

        <div className="text-right">
          <span className="text-[11px] text-[var(--text-tertiary)]">Total Normalized Findings</span>
          <p className="text-[18px] font-mono font-bold" style={{ color: 'var(--text-primary)' }}>
            {totalFindings}
          </p>
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
