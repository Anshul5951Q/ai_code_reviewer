import { ShieldAlert } from 'lucide-react';
import { EmptyState } from '@/components/common/empty-state';
import { SeverityBadge } from '@/components/common/status-badge';
import { truncate } from '@/lib/utils';
import type { Finding } from '@/types/security';

interface CriticalFindingsProps {
  findings: Finding[];
}

export function CriticalFindings({ findings }: CriticalFindingsProps) {
  const criticalAndHigh = findings.filter(
    (f) => f.severity === 'critical' || f.severity === 'high',
  );

  return (
    <div className="card">
      <div className="mb-4">
        <h2
          className="text-[13px] font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          Critical Findings
        </h2>
        <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
          Highest severity open issues
        </p>
      </div>

      {criticalAndHigh.length === 0 ? (
        <EmptyState
          icon={<ShieldAlert size={18} />}
          title="No critical findings"
          description="Critical and high severity findings will appear here."
          className="py-8"
        />
      ) : (
        <ul className="space-y-2">
          {criticalAndHigh.slice(0, 5).map((finding) => (
            <li
              key={finding.id}
              className="flex items-start gap-3 p-3 rounded"
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <SeverityBadge severity={finding.severity} className="mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p
                  className="text-[12px] font-medium"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {truncate(finding.title, 60)}
                </p>
                {finding.file_path && (
                  <p
                    className="mono text-[11px] mt-0.5"
                    style={{ color: 'var(--text-tertiary)' }}
                  >
                    {finding.file_path}
                    {finding.line_number && `:${finding.line_number}`}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
