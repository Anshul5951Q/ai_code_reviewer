import { GitBranch } from 'lucide-react';
import { EmptyState } from '@/components/common/empty-state';
import { formatScore, formatRelativeTime } from '@/lib/utils';
import type { RepositoryHealth } from '@/types/repository';

interface RepositoryHealthProps {
  repositories: RepositoryHealth[];
}

const HEADERS = [
  'Repository',
  'Overall',
  'Security',
  'Quality',
  'Last Review',
  'Status',
] as const;

const STATUS_STYLES = {
  healthy: { color: 'var(--success)', label: 'Healthy' },
  warning: { color: 'var(--warning)', label: 'Warning' },
  critical: { color: 'var(--critical)', label: 'Critical' },
  unknown: { color: 'var(--text-tertiary)', label: 'Unknown' },
} as const;

export function RepositoryHealth({ repositories }: RepositoryHealthProps) {
  return (
    <div className="card">
      <div className="mb-4">
        <h2
          className="text-[13px] font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          Repository Health
        </h2>
        <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
          Analysis scores by repository
        </p>
      </div>

      {repositories.length === 0 ? (
        <EmptyState
          icon={<GitBranch size={18} />}
          title="No repositories analyzed"
          description="Connect repositories and run analysis to see health scores."
          className="py-8"
        />
      ) : (
        <div className="overflow-x-auto -mx-4 px-4">
          <table className="w-full min-w-[600px]">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                {HEADERS.map((h) => (
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
              {repositories.map((repo) => {
                const statusStyle = STATUS_STYLES[repo.status];
                return (
                  <tr
                    key={repo.repository}
                    className="border-b transition-colors hover:bg-white/[0.02]"
                    style={{ borderColor: 'var(--border-subtle)' }}
                  >
                    <td
                      className="py-2.5 pr-4 text-[13px] font-medium"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {repo.repository}
                    </td>
                    <td
                      className="py-2.5 pr-4 text-[13px] tabular-nums"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {formatScore(repo.overall_score)}
                    </td>
                    <td
                      className="py-2.5 pr-4 text-[13px] tabular-nums"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {formatScore(repo.security_score)}
                    </td>
                    <td
                      className="py-2.5 pr-4 text-[13px] tabular-nums"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {formatScore(repo.quality_score)}
                    </td>
                    <td
                      className="py-2.5 pr-4 text-[12px]"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      {formatRelativeTime(repo.last_review)}
                    </td>
                    <td className="py-2.5">
                      <span
                        className="text-[12px] font-medium"
                        style={{ color: statusStyle.color }}
                      >
                        {statusStyle.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
