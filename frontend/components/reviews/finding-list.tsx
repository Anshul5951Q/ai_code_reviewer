'use client';

import { useState, useMemo } from 'react';
import { Search, FileCode, ChevronRight, Sparkles, ShieldCheck, ShieldAlert } from 'lucide-react';
import type { Finding } from '@/types/security';
import { SeverityOverview } from './severity-overview';
import { FindingDetailModal } from './finding-detail-modal';
import { RemediationPanel } from '@/components/remediation/remediation-panel';

interface FindingListProps {
  findings: Finding[];
}

export function FindingList({ findings: initialFindings }: FindingListProps) {
  const [statusOverrides, setStatusOverrides] = useState<Record<string, Finding['status']>>({});
  const [selectedSeverity, setSelectedSeverity] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFinding, setActiveFinding] = useState<Finding | null>(null);
  const [remediatingFinding, setRemediatingFinding] = useState<Finding | null>(null);

  const handleStatusChange = (findingId: string, newStatus: string) => {
    setStatusOverrides((prev) => ({
      ...prev,
      [findingId]: newStatus as Finding['status'],
    }));
  };

  const findings = useMemo(() => {
    return initialFindings.map((f) => ({
      ...f,
      status: statusOverrides[f.id] ?? f.status,
    }));
  }, [initialFindings, statusOverrides]);

  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      if (selectedSeverity && f.severity !== selectedSeverity) return false;
      if (selectedCategory !== 'all' && f.category !== selectedCategory) return false;
      if (selectedStatus !== 'all') {
        if (selectedStatus === 'resolved' && f.status !== 'resolved') return false;
        if (selectedStatus === 'open' && f.status !== 'open') return false;
        if (selectedStatus === 'remediation_in_progress' && f.status !== 'remediation_in_progress') return false;
        if (selectedStatus === 'verification_failed' && f.status !== 'verification_failed') return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchTitle = f.title.toLowerCase().includes(q);
        const matchFile = f.file_path?.toLowerCase().includes(q) ?? false;
        const matchDesc = f.description?.toLowerCase().includes(q) ?? false;
        const matchCwe = f.cwe?.toLowerCase().includes(q) ?? false;
        if (!matchTitle && !matchFile && !matchDesc && !matchCwe) return false;
      }
      return true;
    });
  }, [findings, selectedSeverity, selectedCategory, selectedStatus, searchQuery]);

  const getSeverityBadge = (sev: string) => {
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

  return (
    <div className="card p-5 border border-[var(--border-default)]">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-[15px] font-semibold" style={{ color: 'var(--text-primary)' }}>
            Code & Security Findings
          </h3>
          <p className="text-[12px] text-[var(--text-tertiary)] mt-0.5">
            Normalized, deduplicated findings ranked by confidence and severity.
          </p>
        </div>

        {/* Filter controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status dropdown */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-secondary)] focus:outline-none focus:border-[var(--border-default)]"
          >
            <option value="all">All Statuses</option>
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
            <option value="remediation_in_progress">In Progress</option>
            <option value="verification_failed">Verification Failed</option>
          </select>

          {/* Category dropdown */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-secondary)] focus:outline-none focus:border-[var(--border-default)]"
          >
            <option value="all">All Categories</option>
            <option value="security">Security</option>
            <option value="quality">Quality</option>
            <option value="maintainability">Maintainability</option>
            <option value="architecture">Architecture</option>
          </select>

          {/* Search box */}
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
            <input
              type="text"
              placeholder="Filter findings, files, CWE…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-xs pl-8 pr-3 py-1.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-tertiary)] w-40 focus:w-56 transition-all focus:outline-none focus:border-[var(--border-default)]"
            />
          </div>
        </div>
      </div>

      {/* Severity pill buttons */}
      <SeverityOverview
        findings={findings}
        selectedSeverity={selectedSeverity}
        onSelectSeverity={setSelectedSeverity}
      />

      {/* Finding List */}
      {filteredFindings.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-[var(--border-subtle)] rounded-lg">
          <p className="text-sm font-medium text-[var(--text-secondary)]">No findings match current filters</p>
          <p className="text-xs text-[var(--text-tertiary)] mt-1">
            Try adjusting your search query or severity filters.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredFindings.map((finding) => {
            const lineStr = finding.start_line
              ? finding.end_line && finding.end_line !== finding.start_line
                ? `:${finding.start_line}–${finding.end_line}`
                : `:${finding.start_line}`
              : finding.line_number
              ? `:${finding.line_number}`
              : '';

            const confPct = finding.confidence !== null && finding.confidence !== undefined
              ? `${Math.round(finding.confidence * 100)}%`
              : null;

            const isResolved = finding.status === 'resolved';
            const isInProgress = finding.status === 'remediation_in_progress';
            const isFailed = finding.status === 'verification_failed';

            return (
              <div
                key={finding.id}
                className="flex items-start justify-between gap-4 p-4 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] hover:border-white/20 transition-all group"
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded border ${getSeverityBadge(
                        finding.severity
                      )}`}
                    >
                      {finding.severity}
                    </span>

                    <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-white/5 text-[var(--text-secondary)] capitalize">
                      {finding.category}
                    </span>

                    {/* Remediation Status Pill */}
                    {isResolved ? (
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                        <ShieldCheck size={11} /> Resolved
                      </span>
                    ) : isInProgress ? (
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/30 flex items-center gap-1">
                        <Sparkles size={11} className="animate-spin" /> In Progress
                      </span>
                    ) : isFailed ? (
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30 flex items-center gap-1">
                        <ShieldAlert size={11} /> Verification Failed
                      </span>
                    ) : null}

                    {finding.cwe && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        {finding.cwe}
                      </span>
                    )}

                    {confPct && (
                      <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                        Confidence {confPct}
                      </span>
                    )}

                    <span className="text-[10px] text-[var(--text-tertiary)] font-mono">
                      via {(finding.source ?? 'code_review_agent').replace(/_/g, ' ')}
                    </span>
                  </div>

                  <h4
                    onClick={() => setActiveFinding(finding)}
                    className="text-[14px] font-semibold text-[var(--text-primary)] group-hover:text-emerald-400 transition-colors cursor-pointer"
                  >
                    {finding.title}
                  </h4>

                  {finding.file_path && (
                    <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-mono">
                      <FileCode size={12} className="text-[var(--text-tertiary)] shrink-0" />
                      <span className="truncate">{finding.file_path}</span>
                      <span className="text-[var(--text-tertiary)]">{lineStr}</span>
                    </div>
                  )}

                  {finding.description && (
                    <p className="text-[12px] text-[var(--text-tertiary)] line-clamp-2 leading-relaxed">
                      {finding.description}
                    </p>
                  )}
                </div>

                <div className="shrink-0 flex items-center gap-2">
                  <button
                    onClick={() => setRemediatingFinding(finding)}
                    className={`text-xs py-1.5 px-2.5 rounded-lg flex items-center gap-1 font-medium transition-all shadow-sm ${
                      isResolved
                        ? 'bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30'
                        : 'bg-indigo-600 hover:bg-indigo-500 text-white'
                    }`}
                  >
                    <Sparkles size={12} />
                    <span>{isResolved ? 'Verified Fix' : 'Fix with AI'}</span>
                  </button>

                  <button
                    onClick={() => setActiveFinding(finding)}
                    className="btn btn-secondary text-xs py-1.5 px-3 flex items-center gap-1 hover:bg-white/10"
                  >
                    View
                    <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Finding Detail Modal */}
      <FindingDetailModal
        finding={activeFinding}
        onClose={() => setActiveFinding(null)}
        onStatusChange={handleStatusChange}
      />

      {/* Direct Remediation Panel Modal */}
      {remediatingFinding && (
        <RemediationPanel
          finding={remediatingFinding}
          onClose={() => setRemediatingFinding(null)}
          onStatusChange={(newStatus) => {
            handleStatusChange(remediatingFinding.id, newStatus);
            setRemediatingFinding((prev) => (prev ? { ...prev, status: newStatus as Finding['status'] } : null));
          }}
        />
      )}
    </div>
  );
}
