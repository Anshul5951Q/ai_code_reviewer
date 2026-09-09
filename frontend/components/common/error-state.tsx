import { AlertTriangle, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'An unexpected error occurred. Please try again.',
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-16 px-8 text-center',
        className,
      )}
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
        style={{
          background: 'var(--critical-subtle)',
          border: '1px solid var(--critical-border)',
        }}
      >
        <AlertTriangle size={20} style={{ color: 'var(--critical)' }} />
      </div>
      <h3
        className="text-[14px] font-semibold mb-1"
        style={{ color: 'var(--text-primary)' }}
      >
        {title}
      </h3>
      <p
        className="text-[13px] max-w-xs leading-relaxed"
        style={{ color: 'var(--text-secondary)' }}
      >
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 flex items-center gap-2 px-3 py-1.5 rounded text-[13px] font-medium transition-colors"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)',
            color: 'var(--text-primary)',
          }}
        >
          <RefreshCw size={13} />
          Try again
        </button>
      )}
    </div>
  );
}
