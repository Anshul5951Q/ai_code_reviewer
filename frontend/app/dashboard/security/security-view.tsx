'use client';

import { useEffect, useState, useMemo } from 'react';
import { AlertTriangle, Shield, CheckCircle, ShieldAlert } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { MetricCard } from '@/components/dashboard/metric-card';
import { SecurityScore } from '@/components/security/security-score';
import { SeverityBreakdown } from '@/components/security/severity-breakdown';
import { SecurityTrend } from '@/components/security/security-trend';
import { VulnerabilityCard } from '@/components/security/vulnerability-card';
import { RemediationPanel } from '@/components/remediation/remediation-panel';
import { EmptyState } from '@/components/common/empty-state';
import { LoadingState } from '@/components/common/loading-state';
import { getReviews, getSecurityFindings, getSecuritySummary } from '@/lib/api';
import type { SecuritySummary, Finding } from '@/types/security';
import type { Review } from '@/types/review';

const DEFAULT_SUMMARY: SecuritySummary = {
  overall_score: null,
  critical_count: 0,
  high_count: 0,
  medium_count: 0,
  low_count: 0,
  resolved_count: 0,
  open_count: 0,
  repositories_analyzed: 0,
};

export function SecurityView() {
  const [summary, setSummary] = useState<SecuritySummary>(DEFAULT_SUMMARY);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [activeFinding, setActiveFinding] = useState<Finding | null>(null);

  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      if (statusFilter === 'all') return true;
      if (statusFilter === 'open') return f.status === 'open';
      if (statusFilter === 'resolved') return f.status === 'resolved';
      if (statusFilter === 'remediation_available')
        return f.status === 'remediation_available' || f.status === 'open';
      if (statusFilter === 'verification_failed')
        return f.status === 'verification_failed';
      return true;
    });
  }, [findings, statusFilter]);


  useEffect(() => {
    async function loadSecurityData() {
      setLoading(true);
      try {
        const [sumRes, findRes, revsRes] = await Promise.all([
          getSecuritySummary(),
          getSecurityFindings({ limit: 20 }),
          getReviews({ limit: 10 }),
        ]);
        setSummary(sumRes);
        setFindings(findRes.items);
        setReviews(revsRes.items);
      } catch {
        // Fallback to default zeroed values
      } finally {
        setLoading(false);
      }
    }
    loadSecurityData();
  }, []);

  if (loading) {
    return <LoadingState message="Loading security posture..." />;
  }

  return (
    <div>
      <PageHeader
        title="Security"
        description="Security posture and vulnerability overview across your repositories."
      />

      {/* Top metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <MetricCard
          title="Security Score"
          value={summary.overall_score !== null ? `${summary.overall_score}%` : '—'}
          description={summary.overall_score !== null ? 'Aggregated score' : 'No analysis yet'}
          icon={<Shield size={14} />}
          trend={{ direction: 'neutral', label: summary.overall_score !== null ? 'Live' : 'Pending' }}
        />
        <MetricCard
          title="Critical"
          value={summary.critical_count}
          description="Open vulnerabilities"
          icon={<AlertTriangle size={14} />}
          trend={{ direction: 'neutral', label: 'Active' }}
        />
        <MetricCard
          title="High Severity"
          value={summary.high_count}
          description="Open vulnerabilities"
          icon={<ShieldAlert size={14} />}
          trend={{ direction: 'neutral', label: 'Active' }}
        />
        <MetricCard
          title="Resolved"
          value={summary.resolved_count}
          description="Total remediated"
          icon={<CheckCircle size={14} />}
          trend={{ direction: 'neutral', label: 'Historical' }}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-6">
        <SecurityScore score={summary.overall_score} />
        <SeverityBreakdown summary={summary} />
        <SecurityTrend
          data={reviews
            .filter((r) => r.security_score !== null)
            .slice(-7)
            .map((r) => ({
              date: new Date(r.created_at).toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
              }),
              score: r.security_score,
            }))}
        />
      </div>

      {/* Findings Header & Remediation Filters */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
        <div>
          <h2
            className="text-[13px] font-semibold"
            style={{ color: 'var(--text-primary)' }}
          >
            Vulnerabilities & Remediation
          </h2>
          <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
            Security findings with automated AI remediation and verification.
          </p>
        </div>

        {/* Filter Buttons */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {[
            { key: 'all', label: 'All' },
            { key: 'open', label: 'Open' },
            { key: 'resolved', label: 'Resolved' },
            { key: 'remediation_available', label: 'Remediation Available' },
            { key: 'verification_failed', label: 'Verification Failed' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setStatusFilter(tab.key)}
              className={`text-xs px-2.5 py-1 rounded-md transition-all font-medium whitespace-nowrap ${
                statusFilter === tab.key
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {filteredFindings.length === 0 ? (
        <EmptyState
          icon={<ShieldAlert size={20} />}
          title="No vulnerabilities match current filter"
          description="Try selecting a different status filter or run analysis on additional repositories."
          className="py-16"
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {filteredFindings.map((f) => (
            <VulnerabilityCard
              key={f.id}
              finding={f}
              onRemediate={(finding) => setActiveFinding(finding)}
            />
          ))}
        </div>
      )}

      {/* Remediation Workspace Modal */}
      {activeFinding && (
        <RemediationPanel
          finding={activeFinding}
          onClose={() => setActiveFinding(null)}
          onStatusChange={(newStatus) => {
            setFindings((prev) =>
              prev.map((f) => (f.id === activeFinding.id ? { ...f, status: newStatus as Finding['status'] } : f))
            );
          }}
        />
      )}
    </div>
  );
}

