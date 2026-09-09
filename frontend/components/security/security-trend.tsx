'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { EmptyState } from '@/components/common/empty-state';
import { TrendingUp } from 'lucide-react';

interface SecurityTrendPoint {
  date: string;
  score: number | null;
}

interface SecurityTrendProps {
  data?: SecurityTrendPoint[];
}

export function SecurityTrend({ data = [] }: SecurityTrendProps) {
  const validData = data.filter((d) => d.score !== null && d.score !== undefined);
  const hasData = validData.length > 0;

  return (
    <div className="card">
      <h2 className="text-[13px] font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
        Security Score Trend
      </h2>
      <p className="text-[11px] mb-4" style={{ color: 'var(--text-tertiary)' }}>
        Score history across recent reviews
      </p>

      {hasData ? (
        <ResponsiveContainer width="100%" height={160}>
          <LineChart
            data={validData}
            margin={{ top: 4, right: 0, left: -20, bottom: 0 }}
          >
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
              domain={[0, 100]}
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
            <Line
              type="monotone"
              dataKey="score"
              stroke="#10b981"
              strokeWidth={1.5}
              dot={{ r: 2, fill: '#10b981' }}
              activeDot={{ r: 4, fill: '#10b981' }}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState
          icon={<TrendingUp size={18} />}
          title="No trend data"
          description="Score trend will appear after repository security reviews."
          className="py-8"
        />
      )}
    </div>
  );
}
