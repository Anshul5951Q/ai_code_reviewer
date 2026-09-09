import { ClipboardList } from 'lucide-react';
import { EmptyState } from '@/components/common/empty-state';
import { StatusBadge } from '@/components/common/status-badge';
import { formatScore, shortSha } from '@/lib/utils';
import type { Review } from '@/types/review';

interface RecentReviewsProps {
  reviews: Review[];
}

const TABLE_HEADERS = [
  'Repository',
  'Commit',
  'Score',
  'Findings',
  'Status',
] as const;

export function RecentReviews({ reviews }: RecentReviewsProps) {
  return (
    <div className="card">
      <div className="mb-4">
        <h2
          className="text-[13px] font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          Recent Reviews
        </h2>
        <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
          Latest analysis runs
        </p>
      </div>

      {reviews.length === 0 ? (
        <EmptyState
          icon={<ClipboardList size={18} />}
          title="No reviews yet"
          description="Your recent analysis runs will appear here."
          className="py-8"
        />
      ) : (
        <div className="overflow-x-auto -mx-4 px-4">
          <table className="w-full min-w-[500px]">
            <thead>
              <tr
                style={{ borderBottom: '1px solid var(--border-subtle)' }}
              >
                {TABLE_HEADERS.map((h) => (
                  <th
                    key={h}
                    className="text-left pb-2 text-[11px] font-semibold uppercase tracking-wide"
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
                    className="py-2.5 text-[13px] font-medium pr-4"
                    style={{ color: 'var(--text-primary)' }}
                  >
                    {review.repository_id}
                  </td>
                  <td className="py-2.5 pr-4">
                    <code
                      className="mono text-[12px]"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      {shortSha(review.commit_sha)}
                    </code>
                  </td>
                  <td
                    className="py-2.5 pr-4 text-[13px] tabular-nums"
                    style={{ color: 'var(--text-primary)' }}
                  >
                    {formatScore(review.overall_score)}
                  </td>
                  <td
                    className="py-2.5 pr-4 text-[13px] tabular-nums"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    —
                  </td>
                  <td className="py-2.5">
                    <StatusBadge status={review.status} />
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
