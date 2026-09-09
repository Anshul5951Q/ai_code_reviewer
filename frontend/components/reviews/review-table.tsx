import { StatusBadge } from '@/components/common/status-badge';
import { formatRelativeTime, formatScore, shortSha } from '@/lib/utils';
import type { Review } from '@/types/review';
import { ClipboardList } from 'lucide-react';
import { EmptyState } from '@/components/common/empty-state';

interface ReviewTableProps {
  reviews: Review[];
}

const HEADERS = [
  'Repository',
  'Commit',
  'Branch',
  'Started',
  'Score',
  'Findings',
  'Status',
] as const;

export function ReviewTable({ reviews }: ReviewTableProps) {
  if (reviews.length === 0) {
    return (
      <EmptyState
        icon={<ClipboardList size={20} />}
        title="No reviews found"
        description="Code reviews will appear here once analysis runs are triggered."
        className="py-20"
      />
    );
  }

  return (
    <div className="card overflow-x-auto">
      <table className="w-full min-w-[700px]">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            {HEADERS.map((h) => (
              <th
                key={h}
                className="text-left pb-3 text-[11px] font-semibold uppercase tracking-wide"
                style={{ color: 'var(--text-tertiary)' }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {reviews.map((review) => (
            <tr
              key={review.id}
              className="border-b transition-colors hover:bg-white/[0.02]"
              style={{ borderColor: 'var(--border-subtle)' }}
            >
              <td
                className="py-3 pr-4 text-[13px] font-medium"
                style={{ color: 'var(--text-primary)' }}
              >
                {review.repository_id}
              </td>
              <td className="py-3 pr-4">
                <code className="mono text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                  {shortSha(review.commit_sha)}
                </code>
              </td>
              <td className="py-3 pr-4 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                {review.branch}
              </td>
              <td className="py-3 pr-4 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                {formatRelativeTime(review.started_at)}
              </td>
              <td className="py-3 pr-4 text-[13px] tabular-nums" style={{ color: 'var(--text-primary)' }}>
                {formatScore(review.overall_score)}
              </td>
              <td className="py-3 pr-4 text-[13px] tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                —
              </td>
              <td className="py-3">
                <StatusBadge status={review.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
