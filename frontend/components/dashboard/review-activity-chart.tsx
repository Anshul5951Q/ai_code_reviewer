'use client';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { DEMO_REVIEW_ACTIVITY } from '@/lib/constants';
import { EmptyState } from '@/components/common/empty-state';
import { Activity } from 'lucide-react';

const hasData = DEMO_REVIEW_ACTIVITY.some((d) => d.reviews > 0);

export function ReviewActivityChart() {
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
          <AreaChart data={DEMO_REVIEW_ACTIVITY} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
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
          title="No review data yet"
          description="Connect a repository and run your first analysis to see activity here."
          className="py-8"
        />
      )}
    </div>
  );
}
