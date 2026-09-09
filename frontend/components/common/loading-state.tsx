import { cn } from '@/lib/utils';

interface LoadingStateProps {
  rows?: number;
  className?: string;
  message?: string;
}

function SkeletonLine({ width = 'w-full', height = 'h-4' }: { width?: string; height?: string }) {
  return (
    <div
      className={cn('rounded animate-pulse', width, height)}
      style={{ background: 'var(--bg-elevated)' }}
    />
  );
}

export function LoadingState({ rows = 3, className, message }: LoadingStateProps) {
  return (
    <div className={cn('space-y-3', className)} role="status" aria-label={message ?? 'Loading'}>
      {message && (
        <p className="text-[12px] font-medium animate-pulse mb-2" style={{ color: 'var(--text-secondary)' }}>
          {message}
        </p>
      )}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="space-y-2">
          <SkeletonLine width="w-2/3" />
          <SkeletonLine width="w-full" />
        </div>
      ))}
      <span className="sr-only">{message ?? 'Loading…'}</span>
    </div>
  );
}

export function LoadingCard({ className }: { className?: string }) {
  return (
    <div
      className={cn('card', className)}
      style={{ minHeight: 120 }}
      role="status"
      aria-label="Loading"
    >
      <div className="space-y-3">
        <SkeletonLine width="w-1/3" height="h-3" />
        <SkeletonLine width="w-full" height="h-8" />
        <SkeletonLine width="w-1/2" height="h-3" />
      </div>
    </div>
  );
}

export function LoadingTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-px" role="status" aria-label="Loading table">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 px-4 py-3 rounded animate-pulse"
          style={{ background: 'var(--bg-surface)' }}
        >
          <SkeletonLine width="w-1/4" height="h-3" />
          <SkeletonLine width="w-1/6" height="h-3" />
          <SkeletonLine width="w-1/6" height="h-3" />
          <SkeletonLine width="w-1/6" height="h-3" />
          <SkeletonLine width="w-1/8" height="h-5" />
        </div>
      ))}
    </div>
  );
}
