import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-16 px-8 text-center',
        className,
      )}
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)' }}
      >
        <span style={{ color: 'var(--text-tertiary)' }}>{icon}</span>
      </div>
      <h3
        className="text-[14px] font-semibold mb-1"
        style={{ color: 'var(--text-primary)' }}
      >
        {title}
      </h3>
      {description && (
        <p
          className="text-[13px] max-w-xs leading-relaxed mb-4"
          style={{ color: 'var(--text-secondary)' }}
        >
          {description}
        </p>
      )}
      {action}
    </div>
  );
}
