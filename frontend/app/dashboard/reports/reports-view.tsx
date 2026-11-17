'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { FileText, Search } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { LoadingState } from '@/components/common/loading-state';
import { EmptyState } from '@/components/common/empty-state';
import { StatusBadge } from '@/components/common/status-badge';
import { ApiClientError, getRepositories, getReviews } from '@/lib/api';
import { formatRelativeTime, formatScore, shortSha } from '@/lib/utils';
import type { Review } from '@/types/review';

// A report exists once analysis has produced results.
const REPORT_STATUSES = ['completed', 'completed_with_warnings'];

export function ReportsView() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [repoNames, setRepoNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        const [reviewRes, repoRes] = await Promise.all([
          getReviews({ limit: 100 }),
          getRepositories({ limit: 100 }).catch(() => null),
        ]);
        if (ignore) return;
        setReviews(reviewRes.items.filter((r) => REPORT_STATUSES.includes(r.status)));
        if (repoRes) {
          setRepoNames(Object.fromEntries(repoRes.items.map((r) => [r.id, r.full_name || r.name])));
        }
      } catch (e) {
        if (!ignore) setError(e instanceof ApiClientError ? e.detail : 'Failed to load reports');
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void load();
    return () => {
      ignore = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = q
      ? reviews.filter((r) =>
          [repoNames[r.repository_id] ?? '', r.branch, r.commit_sha].some((v) =>
            v.toLowerCase().includes(q)
          )
        )
      : reviews;
    return [...list].sort(
      (a, b) =>
        new Date(b.completed_at ?? b.created_at).getTime() -
        new Date(a.completed_at ?? a.created_at).getTime()
    );
  }, [reviews, repoNames, search]);

  return (
    <div>
      <PageHeader
        title="Reports"
        description="Generated AI code review reports for every completed analysis."
      />

      <div className="relative mb-4 max-w-sm">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2"
          style={{ color: 'var(--text-tertiary)' }}
        />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by repository, branch or commit"
          className="w-full pl-9 pr-3 py-2 rounded text-[13px]"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)',
            color: 'var(--text-primary)',
          }}
        />
      </div>

      {loading ? (
        <LoadingState message="Loading reports..." />
      ) : error ? (
        <div
          className="p-6 rounded-lg text-center my-6 text-[13px]"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)',
            color: 'var(--text-secondary)',
          }}
        >
          {error}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<FileText size={20} />}
          title="No reports yet"
          description="Reports appear here once a code review analysis completes."
          className="py-20"
        />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[800px]">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                {['Repository', 'Commit', 'Branch', 'Generated', 'Overall', 'Security', 'Quality', 'Status', ''].map(
                  (h) => (
                    <th
                      key={h}
                      className="text-left pb-3 pr-4 text-[11px] font-semibold uppercase tracking-wide"
                      style={{ color: 'var(--text-tertiary)' }}
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr
                  key={r.id}
                  className="border-b transition-colors hover:bg-white/[0.02]"
                  style={{ borderColor: 'var(--border-subtle)' }}
                >
                  <td className="py-3 pr-4 text-[13px] font-medium" style={{ color: 'var(--text-primary)' }}>
                    {repoNames[r.repository_id] ?? `${r.repository_id.slice(0, 8)}…`}
                  </td>
                  <td className="py-3 pr-4">
                    <code className="mono text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                      {shortSha(r.commit_sha)}
                    </code>
                  </td>
                  <td className="py-3 pr-4 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                    {r.branch}
                  </td>
                  <td className="py-3 pr-4 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                    {formatRelativeTime(r.completed_at ?? r.created_at)}
                  </td>
                  <td className="py-3 pr-4 text-[13px] tabular-nums" style={{ color: 'var(--text-primary)' }}>
                    {formatScore(r.overall_score)}
                  </td>
                  <td className="py-3 pr-4 text-[13px] tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                    {formatScore(r.security_score)}
                  </td>
                  <td className="py-3 pr-4 text-[13px] tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                    {formatScore(r.quality_score)}
                  </td>
                  <td className="py-3 pr-4">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="py-3 text-right">
                    <Link
                      href={`/dashboard/reports/${r.id}`}
                      className="btn btn-ghost inline-flex items-center gap-1.5 text-xs py-1.5 px-2.5"
                    >
                      <FileText size={13} />
                      View Report
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
