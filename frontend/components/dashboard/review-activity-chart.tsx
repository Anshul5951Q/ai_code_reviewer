'use client';

import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { EmptyState } from '@/components/common/empty-state';
import { Activity } from 'lucide-react';
import type { Review } from '@/types/review';

interface ReviewActivityChartProps {
  reviews?: Review[];
}

export function ReviewActivityChart({ reviews = [] }: ReviewActivityChartProps) {
  const chartData = useMemo(() => {
    // Generate dates for the last 7 days
    const days: Array<{ date: string; fullDate: string; reviews: number }> = [];
    const now = new Date();
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const label = d.toLocaleDateString(undefined, { weekday: 'short' });
      const dateStr = d.toISOString().split('T')[0];
      days.push({
        date: label,
        fullDate: dateStr,
        reviews: 0,
      });
    }

    // Tally reviews by creation date
    for (const rev of reviews) {
      if (rev.created_at) {
        const revDate = new Date(rev.created_at).toISOString().split('T')[0];
        const match = days.find((day) => day.fullDate === revDate);
        if (match) {
          match.reviews += 1;
        }
      }
    }

    return days;
  }, [reviews]);

  const hasData = reviews.length > 0;

  return (
    <div className="card">
      <div className="mb-4">
        <h2
          className="text-[13px] font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          Review Activity
        </h2>
        <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
          Reviews completed over the last 7 days
        </p>
      </div>

      {hasData ? (
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={chartData} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="reviewGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              dataKey="reviews"
              tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }}
              axisLine={false}
              tickLine={false}
              allowDecimals={false}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                borderRadius: 6,
                fontSize: 12,
                color: 'var(--text-primary)',
              }}
              cursor={{ stroke: 'var(--border-strong)' }}
            />
            <Area
              type="monotone"
              dataKey="reviews"
              stroke="#6366f1"
              strokeWidth={1.5}
              fill="url(#reviewGradient)"
              dot={false}
              activeDot={{ r: 3, fill: '#6366f1' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState
          icon={<Activity size={18} />}
          title="No review activity yet"
          description="Connect a repository and run your first analysis to see activity here."
          className="py-8"
        />
      )}
    </div>
  );
}
