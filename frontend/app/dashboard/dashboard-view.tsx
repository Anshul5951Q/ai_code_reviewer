'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import {
  GitBranch,
  ClipboardList,
  AlertTriangle,
  ShieldCheck,
  ScanSearch,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { MetricCard } from '@/components/dashboard/metric-card';
import { RecentReviews } from '@/components/dashboard/recent-reviews';
import { CriticalFindings } from '@/components/dashboard/critical-findings';
import { RepositoryHealth } from '@/components/dashboard/repository-health';
import { ChartSkeleton } from '@/components/common/chart-skeleton';
import { DashboardSkeleton } from '@/components/dashboard/dashboard-skeleton';
import {
  getRepositories,
  getReviews,
  getSecurityFindings,
  getSecuritySummary,
} from '@/lib/api';
import type { Repository, RepositoryHealth as RepoHealth } from '@/types/repository';
import type { Review } from '@/types/review';
import type { Finding, SecuritySummary } from '@/types/security';

// Code-split heavy chart libraries
const ReviewActivityChart = dynamic(
  () =>
    import('@/components/dashboard/review-activity-chart').then(
      (mod) => mod.ReviewActivityChart,
    ),
  {
    loading: () => <ChartSkeleton height={160} />,
    ssr: false,
  },
);

const SecurityTrendChart = dynamic(
  () =>
    import('@/components/dashboard/security-trend-chart').then(
      (mod) => mod.SecurityTrendChart,
    ),
  {
    loading: () => <ChartSkeleton height={160} />,
    ssr: false,
  },
);

export function DashboardView() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [summary, setSummary] = useState<SecuritySummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      try {
        const [reposRes, reviewsRes, findingsRes, summaryRes] = await Promise.all([
          getRepositories(),
          getReviews({ limit: 10 }),
          getSecurityFindings({ limit: 10 }),
          getSecuritySummary(),
        ]);
        setRepositories(reposRes.items);
        setReviews(reviewsRes.items);
        setFindings(findingsRes.items);
        setSummary(summaryRes);
      } catch {
        // Fallbacks
      } finally {
        setLoading(false);
      }
    }
    loadDashboard();
  }, []);

  const completedReviewsCount = useMemo(
    () => reviews.filter((r) => r.status === 'completed').length,
    [reviews],
  );

  const repoHealthItems: RepoHealth[] = useMemo(() => {
    return repositories.map((r) => {
      const repoReviews = reviews.filter((rev) => rev.repository_id === r.id);
      const latestReview = repoReviews[0];
      return {
        repository: r.full_name,
        overall_score: latestReview?.overall_score ?? null,
        security_score: latestReview?.security_score ?? null,
        quality_score: latestReview?.quality_score ?? null,
        last_review: latestReview?.created_at ?? null,
        status: latestReview
          ? (latestReview.overall_score ?? 100) > 80
            ? 'healthy'
            : (latestReview.overall_score ?? 100) > 60
            ? 'warning'
            : 'critical'
          : 'unknown',
      };
    });
  }, [repositories, reviews]);

  if (loading) {
    return <DashboardSkeleton />;
  }

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Monitor the quality, security, and health of your repositories."
        actions={
          <Link
            href="/dashboard/reviewer"
            className="flex items-center gap-2 px-3 py-1.5 rounded text-[13px] font-medium transition-all"
            style={{
              background: 'var(--primary)',
              color: 'white',
            }}
          >
            <ScanSearch size={13} />
            Analyze Repository
          </Link>
        }
      />

      {/* Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
        <MetricCard
          title="Repositories"
          value={repositories.length}
          description={repositories.length > 0 ? 'Connected in workspace' : 'No repositories connected'}
          icon={<GitBranch size={14} />}
          trend={{ direction: 'neutral', label: repositories.length > 0 ? 'Active' : 'Connect GitHub' }}
        />
        <MetricCard
          title="Reviews Completed"
          value={completedReviewsCount}
          description="All time"
          icon={<ClipboardList size={14} />}
          trend={{ direction: 'neutral', label: reviews.length > 0 ? `${reviews.length} total` : 'No data yet' }}
        />
        <MetricCard
          title="Open Findings"
          value={summary?.open_count ?? 0}
          description="Across repositories"
          icon={<AlertTriangle size={14} />}
          trend={{ direction: 'neutral', label: (summary?.critical_count ?? 0) > 0 ? `${summary?.critical_count} critical` : 'Clean' }}
        />
        <MetricCard
          title="Resolved"
          value={summary?.resolved_count ?? 0}
          description="Verified remediations"
          icon={<ShieldCheck size={14} />}
          trend={{ direction: 'neutral', label: (summary?.resolved_count ?? 0) > 0 ? `${summary?.resolved_count} fixed` : 'No fixes yet' }}
        />
        <MetricCard
          title="Verification Success"
          value={
            summary?.verification_success_rate !== null && summary?.verification_success_rate !== undefined
              ? `${summary.verification_success_rate}%`
              : '—'
          }
          description={
            summary?.verification_success_rate !== null && summary?.verification_success_rate !== undefined
              ? 'Verification Success'
              : 'No remediation data yet'
          }
          icon={<ShieldCheck size={14} />}
          trend={{
            direction: 'neutral',
            label:
              summary?.verification_success_rate !== null && summary?.verification_success_rate !== undefined
                ? `${summary.remediation_runs_count ?? 0} runs`
                : 'No remediation data yet',
          }}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-6">
        <ReviewActivityChart reviews={reviews} />
        <SecurityTrendChart
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

      {/* Lower Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-6">
        <RecentReviews reviews={reviews} />
        <CriticalFindings findings={findings} />
      </div>

      {/* Repository Health */}
      <RepositoryHealth repositories={repoHealthItems} />
    </div>
  );
}
