'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import {
  Search,
  FileCode,
  Layers,
  ListFilter,
  Network,
  RefreshCw,
} from 'lucide-react';
import type { Finding, CorrelatedFinding, CorrelationStatus, RelationshipType } from '@/types/security';
import { getCorrelatedFindings, getCorrelationStatus, triggerCorrelation } from '@/lib/api';
import { SeverityOverview } from './severity-overview';
import dynamic from 'next/dynamic';

const FindingDetailModal = dynamic(
  () => import('./finding-detail-modal').then((mod) => mod.FindingDetailModal),
  { ssr: false },
);

interface FindingListProps {
  findings: Finding[];
  reviewId?: string;
}

export function FindingList({ findings: initialFindings, reviewId }: FindingListProps) {
  const [viewMode, setViewMode] = useState<'correlated' | 'raw'>('correlated');
  const [statusOverrides, setStatusOverrides] = useState<Record<string, Finding['status']>>({});
  const [selectedSeverity, setSelectedSeverity] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedRelationship, setSelectedRelationship] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Active modal targets
  const [activeFinding, setActiveFinding] = useState<Finding | null>(null);
  const [activeCorrelatedFinding, setActiveCorrelatedFinding] = useState<CorrelatedFinding | null>(null);

  // Correlated findings state
  const [correlatedList, setCorrelatedList] = useState<CorrelatedFinding[]>([]);
  const [corrStatus, setCorrStatus] = useState<CorrelationStatus | null>(null);
  const [loadingCorrelated, setLoadingCorrelated] = useState(false);
  const [correlating, setCorrelating] = useState(false);

  const fetchCorrelatedData = useCallback(async () => {
    if (!reviewId) return;
    try {
      const [corrRes, statusRes] = await Promise.all([
        getCorrelatedFindings(reviewId, { limit: 100 }),
        getCorrelationStatus(reviewId),
      ]);
      setCorrelatedList(corrRes.items);
      setCorrStatus(statusRes);
    } catch {
      // Fallback silently to raw findings if correlated endpoints are not yet available
    } finally {
      setLoadingCorrelated(false);
    }
  }, [reviewId]);

  useEffect(() => {
    let isMounted = true;
    if (reviewId) {
      Promise.all([
        getCorrelatedFindings(reviewId, { limit: 100 }),
        getCorrelationStatus(reviewId),
      ])
        .then(([corrRes, statusRes]) => {
          if (isMounted) {
            setCorrelatedList(corrRes.items);
            setCorrStatus(statusRes);
            setLoadingCorrelated(false);
          }
        })
        .catch(() => {
          if (isMounted) setLoadingCorrelated(false);
        });
    }
    return () => {
      isMounted = false;
    };
  }, [reviewId]);

  const handleManualCorrelation = async () => {
    if (!reviewId) return;
    setCorrelating(true);
    try {
      await triggerCorrelation(reviewId);
      await fetchCorrelatedData();
    } catch {
      // Handle error gracefully
    } finally {
      setCorrelating(false);
    }
  };

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

  // Filter raw findings
  const filteredRawFindings = useMemo(() => {
    return findings.filter((f) => {
      if (selectedSeverity && f.severity !== selectedSeverity) return false;
      if (selectedCategory !== 'all' && f.category !== selectedCategory) return false;
      if (selectedStatus !== 'all') {
        if (selectedStatus === 'resolved' && f.status !== 'resolved') return false;
        if (selectedStatus === 'open' && f.status !== 'open') return false;
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

  // Filter correlated findings
  const filteredCorrelatedFindings = useMemo(() => {
    return correlatedList.filter((cf) => {
      if (selectedSeverity && cf.severity !== selectedSeverity) return false;
      if (selectedCategory !== 'all' && cf.category !== selectedCategory) return false;
      if (selectedStatus !== 'all') {
        if (selectedStatus === 'resolved' && cf.status !== 'resolved') return false;
        if (selectedStatus === 'open' && cf.status !== 'open') return false;
      }
      if (selectedRelationship !== 'all') {
        const hasRel = cf.relationships?.some((r) => r.relationship_type === selectedRelationship);
        if (!hasRel) return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchTitle = cf.title.toLowerCase().includes(q);
        const matchFile = cf.file_path?.toLowerCase().includes(q) ?? false;
        const matchDesc = cf.description?.toLowerCase().includes(q) ?? false;
        const matchRoot = cf.root_cause?.toLowerCase().includes(q) ?? false;
        const matchCwe = cf.cwe?.toLowerCase().includes(q) ?? false;
        if (!matchTitle && !matchFile && !matchDesc && !matchRoot && !matchCwe) return false;
      }
      return true;
    });
  }, [correlatedList, selectedSeverity, selectedCategory, selectedStatus, selectedRelationship, searchQuery]);

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

  const getRelationshipBadge = (relType: RelationshipType) => {
    switch (relType) {
      case 'exact_duplicate':
        return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
      case 'shared_root_cause':
        return 'bg-purple-500/15 text-purple-400 border-purple-500/30';
      case 'overlapping':
        return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
      case 'related':
        return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
      default:
        return 'bg-slate-500/15 text-slate-400 border-slate-500/30';
    }
  };

  return (
    <div className="card p-5 border border-[var(--border-default)]">
      {/* Top Header & View Mode Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4 pb-4 border-b border-[var(--border-subtle)]">
        <div>
          <div className="flex items-center gap-2.5">
            <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
              Findings Intelligence
            </h3>
            {corrStatus && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                v{corrStatus.correlation_version} Correlated
              </span>
            )}
          </div>
          <p className="text-[12px] text-[var(--text-tertiary)] mt-0.5">
            Cross-agent deduplication, overlapping concern linkage, and root-cause intelligence.
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-2">
          <div className="flex items-center p-0.5 bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded-lg text-xs font-medium">
            <button
              onClick={() => setViewMode('correlated')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
                viewMode === 'correlated'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-[var(--text-secondary)] hover:text-white'
              }`}
            >
              <Layers size={13} />
              <span>Unified Issues ({correlatedList.length})</span>
            </button>

            <button
              onClick={() => setViewMode('raw')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
                viewMode === 'raw'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-[var(--text-secondary)] hover:text-white'
              }`}
            >
              <ListFilter size={13} />
              <span>Raw Findings ({findings.length})</span>
            </button>
          </div>

          {reviewId && (
            <button
              onClick={() => void handleManualCorrelation()}
              disabled={correlating}
              title="Re-run Finding Correlation"
              className="p-1.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-white hover:border-[var(--border-default)] transition-colors disabled:opacity-50"
            >
              <RefreshCw size={13} className={correlating ? 'animate-spin' : ''} />
            </button>
          )}
        </div>
      </div>

      {/* Correlation Telemetry Summary Banner */}
      {viewMode === 'correlated' && corrStatus && (
        <div className="mb-4 p-3 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 text-purple-300 font-medium">
              <Network size={13} />
              <span>{corrStatus.total_raw_findings} raw findings grouped into {corrStatus.correlated_clusters_count} unified issues</span>
            </div>
            <span className="text-[var(--border-default)]">•</span>
            <span className="text-emerald-400 font-mono">{corrStatus.exact_duplicates_count} exact duplicates merged</span>
            <span className="text-[var(--border-default)]">•</span>
            <span className="text-amber-400 font-mono">{corrStatus.overlapping_count} overlapping concerns linked</span>
            <span className="text-[var(--border-default)]">•</span>
            <span className="text-purple-400 font-mono">{corrStatus.shared_root_cause_count} shared root causes identified</span>
          </div>

          {corrStatus.semantic_evaluated && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              Ollama Semantic Reasoning Active
            </span>
          )}
        </div>
      )}

      {/* Filter controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
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

          {/* Relationship dropdown (in correlated mode) */}
          {viewMode === 'correlated' && (
            <select
              value={selectedRelationship}
              onChange={(e) => setSelectedRelationship(e.target.value)}
              className="text-xs px-2.5 py-1.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-secondary)] focus:outline-none focus:border-[var(--border-default)]"
            >
              <option value="all">All Relationships</option>
              <option value="exact_duplicate">Exact Duplicate</option>
              <option value="shared_root_cause">Shared Root Cause</option>
              <option value="overlapping">Overlapping</option>
              <option value="related">Related</option>
              <option value="independent">Independent</option>
            </select>
          )}

          {/* Search box */}
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
            <input
              type="text"
              placeholder="Search issues, root cause, files…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-xs pl-8 pr-3 py-1.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-secondary)] placeholder-[var(--text-tertiary)] focus:outline-none focus:border-[var(--border-default)] w-56"
            />
          </div>
        </div>
      </div>

      {/* Severity Breakdown Bar */}
      <div className="mb-4">
        <SeverityOverview
          findings={viewMode === 'correlated' ? (correlatedList as unknown as Finding[]) : findings}
          selectedSeverity={selectedSeverity}
          onSelectSeverity={setSelectedSeverity}
        />
      </div>

      {/* Loading state for correlated view */}
      {viewMode === 'correlated' && loadingCorrelated && (
        <div className="py-12 text-center text-xs text-[var(--text-secondary)]">
          Loading correlated cross-agent findings…
        </div>
      )}

      {/* Correlated Findings List */}
      {viewMode === 'correlated' && !loadingCorrelated && (
        <div className="space-y-3">
          {filteredCorrelatedFindings.length === 0 ? (
            <div className="py-12 text-center text-xs text-[var(--text-tertiary)] border border-dashed border-[var(--border-subtle)] rounded-lg">
              No correlated issues match your active filters.
            </div>
          ) : (
            filteredCorrelatedFindings.map((cf) => {
              const lineStr = cf.start_line
                ? cf.end_line && cf.end_line !== cf.start_line
                  ? `:${cf.start_line}-${cf.end_line}`
                  : `:${cf.start_line}`
                : cf.line_number
                ? `:${cf.line_number}`
                : '';

              const confPct = cf.confidence ? `${Math.round(cf.confidence * 100)}%` : null;

              // Extract distinct relationship types for badges
              const relTypes = Array.from(new Set(cf.relationships?.map((r) => r.relationship_type) ?? []));

              return (
                <div
                  key={cf.id}
                  className="flex items-start justify-between gap-4 p-4 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] hover:border-purple-500/30 transition-all group"
                >
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded border ${getSeverityBadge(
                          cf.severity
                        )}`}
                      >
                        {cf.severity}
                      </span>

                      <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-white/5 text-[var(--text-secondary)] capitalize">
                        {cf.category}
                      </span>

                      {/* Relationship Badges */}
                      {relTypes.map((rt) => (
                        <span
                          key={rt}
                          className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded border ${getRelationshipBadge(
                            rt
                          )}`}
                        >
                          {rt.replace(/_/g, ' ')}
                        </span>
                      ))}

                      {cf.relationships && cf.relationships.length > 1 && (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                          {cf.relationships.length} sources unified
                        </span>
                      )}

                      {cf.cwe && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                          {cf.cwe}
                        </span>
                      )}

                      {confPct && (
                        <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                          Confidence {confPct}
                        </span>
                      )}
                    </div>

                    <h4
                      onClick={() => setActiveCorrelatedFinding(cf)}
                      className="text-[14px] font-semibold text-[var(--text-primary)] group-hover:text-purple-400 transition-colors cursor-pointer"
                    >
                      {cf.title}
                    </h4>

                    {/* Root Cause Callout if identified */}
                    {cf.root_cause && (
                      <div className="text-[11px] text-purple-300/90 font-mono bg-purple-500/10 px-2 py-1 rounded border border-purple-500/20 truncate">
                        Root Cause: {cf.root_cause}
                      </div>
                    )}

                    {cf.file_path && (
                      <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-mono">
                        <FileCode size={12} className="text-[var(--text-tertiary)] shrink-0" />
                        <span className="truncate">{cf.file_path}</span>
                        <span className="text-[var(--text-tertiary)]">{lineStr}</span>
                      </div>
                    )}

                    {cf.description && (
                      <p className="text-[12px] text-[var(--text-tertiary)] line-clamp-2 leading-relaxed">
                        {cf.description}
                      </p>
                    )}
                  </div>

                  <div className="shrink-0 flex items-center gap-2">
                    <button
                      onClick={() => setActiveCorrelatedFinding(cf)}
                      className="btn btn-secondary text-xs py-1.5 px-3 flex items-center gap-1 hover:bg-white/10"
                    >
                      <span>Inspect Details</span>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Raw Findings List */}
      {viewMode === 'raw' && (
        <div className="space-y-3">
          {filteredRawFindings.length === 0 ? (
            <div className="py-12 text-center text-xs text-[var(--text-tertiary)] border border-dashed border-[var(--border-subtle)] rounded-lg">
              No raw findings match your active filters.
            </div>
          ) : (
            filteredRawFindings.map((finding) => {
              const lineStr = finding.start_line
                ? finding.end_line && finding.end_line !== finding.start_line
                  ? `:${finding.start_line}-${finding.end_line}`
                  : `:${finding.start_line}`
                : finding.line_number
                ? `:${finding.line_number}`
                : '';

              const confPct =
                finding.confidence !== null && finding.confidence !== undefined
                  ? `${Math.round(finding.confidence * 100)}%`
                  : null;

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
                      onClick={() => setActiveFinding(finding)}
                      className="btn btn-secondary text-xs py-1.5 px-3 flex items-center gap-1 hover:bg-white/10"
                    >
                      <span>View Raw</span>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Finding Detail Modal (Supports raw finding and correlated finding) */}
      {(activeFinding || activeCorrelatedFinding) && (
        <FindingDetailModal
          finding={activeFinding}
          correlatedFinding={activeCorrelatedFinding}
          onClose={() => {
            setActiveFinding(null);
            setActiveCorrelatedFinding(null);
          }}
          onStatusChange={handleStatusChange}
        />
      )}
    </div>
  );
}
