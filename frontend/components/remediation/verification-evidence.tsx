'use client';

import { CheckCircle, AlertTriangle, Info } from 'lucide-react';

interface VerificationEvidenceProps {
  evidence: string[];
  newFindings?: Array<{
    category?: string;
    severity?: string;
    title?: string;
    description?: string;
  }>;
}

export function VerificationEvidence({
  evidence,
  newFindings = [],
}: VerificationEvidenceProps) {
  return (
    <div className="space-y-4">
      {/* Evidence List */}
      <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg">
        <div className="flex items-center gap-2 mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          <Info className="w-4 h-4 text-blue-400" />
          <span>Independent Verification Evidence</span>
        </div>

        {evidence.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)] italic">
            No specific evidence items recorded.
          </p>
        ) : (
          <ul className="space-y-2">
            {evidence.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                <CheckCircle className="w-3.5 h-3.5 mt-0.5 text-emerald-400 flex-shrink-0" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* New Findings (Regressions) */}
      {newFindings.length > 0 && (
        <div className="p-4 bg-amber-950/20 border border-amber-500/30 rounded-lg">
          <div className="flex items-center gap-2 mb-3 text-xs font-semibold uppercase tracking-wider text-amber-400">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Regressions / New Issues Introduced</span>
          </div>

          <div className="space-y-2">
            {newFindings.map((finding, idx) => (
              <div
                key={idx}
                className="p-3 bg-black/30 border border-amber-500/20 rounded text-xs"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-amber-200">
                    {finding.title || 'Introduced issue'}
                  </span>
                  {finding.severity && (
                    <span className="px-1.5 py-0.5 text-[10px] rounded bg-amber-500/20 text-amber-300 uppercase font-mono">
                      {finding.severity}
                    </span>
                  )}
                </div>
                {finding.description && (
                  <p className="text-slate-300 text-[11px] mt-1">
                    {finding.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
