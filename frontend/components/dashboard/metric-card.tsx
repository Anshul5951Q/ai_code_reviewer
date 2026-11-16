import { memo, type ReactNode } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

type TrendDirection = 'up' | 'down' | 'neutral';

interface MetricCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon: ReactNode;
  trend?: {
    direction: TrendDirection;
    label: string;
  };
  className?: string;
}

const TREND_STYLES: Record<TrendDirection, { color: string; Icon: typeof TrendingUp }> = {
  up: { color: 'var(--success)', Icon: TrendingUp },
  down: { color: 'var(--critical)', Icon: TrendingDown },
  neutral: { color: 'var(--text-tertiary)', Icon: Minus },
};

export const MetricCard = memo(function MetricCard({
  title,
  value,
  description,
  icon,
  trend,
  className,
}: MetricCardProps) {
  const trendStyle = trend ? TREND_STYLES[trend.direction] : null;

  return (
    <div className={cn('card flex flex-col gap-3', className)}>
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span
          className="text-[12px] font-medium uppercase tracking-wide"
          style={{ color: 'var(--text-tertiary)' }}
        >
          {title}
        </span>
        <div
          className="w-7 h-7 rounded flex items-center justify-center"
          style={{ background: 'var(--bg-elevated)' }}
        >
          <span style={{ color: 'var(--text-tertiary)' }}>{icon}</span>
        </div>
      </div>

      {/* Value */}
      <div>
        <span
          className="text-2xl font-semibold tabular-nums"
          style={{ color: 'var(--text-primary)' }}
        >
          {value}
        </span>
      </div>

      {/* Footer row */}
      <div className="flex items-center justify-between mt-auto pt-2" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        {description && (
          <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
            {description}
          </span>
        )}
        {trendStyle && trend && (
          <span
            className="flex items-center gap-0.5 text-[11px] font-medium"
            style={{ color: trendStyle.color }}
          >
            <trendStyle.Icon size={11} />
            {trend.label}
          </span>
        )}
      </div>
    </div>
  );
});
