import { cn } from '@/lib/utils';
import { SEVERITY_CONFIG, STATUS_CONFIG } from '@/lib/constants';
import type { Severity } from '@/types/security';
import type { ReviewStatus } from '@/types/review';

// ---------------------------------------------------------------------------
// Review Status Badge
// ---------------------------------------------------------------------------

interface StatusBadgeProps {
  status: ReviewStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium',
        className,
      )}
      style={{ background: config.bgColor, color: config.color }}
    >
      <span
        className={cn(
          'w-1.5 h-1.5 rounded-full flex-shrink-0',
          status === 'running' && 'status-dot-running',
        )}
        style={{ background: config.dotColor }}
      />
      {config.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Severity Badge
// ---------------------------------------------------------------------------

interface SeverityBadgeProps {
  severity: Severity;
  className?: string;
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  const config = SEVERITY_CONFIG[severity];
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wide',
        className,
      )}
      style={{
        background: config.bgColor,
        color: config.color,
        border: `1px solid ${config.borderColor}`,
      }}
    >
      {config.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Generic Label Badge
// ---------------------------------------------------------------------------

interface LabelBadgeProps {
  label: string;
  variant?: 'default' | 'outline';
  className?: string;
}

export function LabelBadge({
  label,
  variant = 'default',
  className,
}: LabelBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium',
        className,
      )}
      style={
        variant === 'outline'
          ? {
              border: '1px solid var(--border-default)',
              color: 'var(--text-secondary)',
            }
          : {
              background: 'var(--bg-elevated)',
              color: 'var(--text-secondary)',
            }
      }
    >
      {label}
    </span>
  );
}
