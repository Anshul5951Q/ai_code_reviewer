import { StatusBadge } from '@/components/common/status-badge';
import { formatRelativeTime, formatScore, shortSha } from '@/lib/utils';
import type { Review } from '@/types/review';

interface ReviewCardProps {
  review: Review;
}

export function ReviewCard({ review }: ReviewCardProps) {
  return (
    <div
      className="card hover:border-white/10 transition-all"
      style={{ borderColor: 'var(--border-subtle)' }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <p
            className="text-[13px] font-semibold"
            style={{ color: 'var(--text-primary)' }}
          >
            {review.repository_id}
          </p>
          <code
            className="mono text-[11px] mt-0.5"
            style={{ color: 'var(--text-tertiary)' }}
          >
            {review.branch} @ {shortSha(review.commit_sha)}
          </code>
        </div>
        <StatusBadge status={review.status} />
      </div>

      <div
        className="flex items-center gap-4 pt-2"
        style={{ borderTop: '1px solid var(--border-subtle)' }}
      >
        <div>
          <span className="block text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-disabled)' }}>
            Score
          </span>
          <span className="text-[13px] font-semibold tabular-nums" style={{ color: 'var(--text-primary)' }}>
            {formatScore(review.overall_score)}
          </span>
        </div>
        <div>
          <span className="block text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-disabled)' }}>
            Started
          </span>
          <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
            {formatRelativeTime(review.started_at)}
          </span>
        </div>
      </div>
    </div>
  );
}
