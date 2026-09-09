'use client';

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { SecuritySummary } from '@/types/security';
import { EmptyState } from '@/components/common/empty-state';
import { ShieldAlert } from 'lucide-react';

interface SeverityBreakdownProps {
  summary: SecuritySummary;
}

export function SeverityBreakdown({ summary }: SeverityBreakdownProps) {
  const data = [
    { name: 'Critical', value: summary.critical_count, color: '#ef4444' },
    { name: 'High', value: summary.high_count, color: '#f97316' },
    { name: 'Medium', value: summary.medium_count, color: '#f59e0b' },
    { name: 'Low', value: summary.low_count, color: '#60a5fa' },
  ].filter((d) => d.value > 0);

  const total =
    summary.critical_count +
    summary.high_count +
    summary.medium_count +
    summary.low_count;

  return (
    <div className="card">
      <h2 className="text-[13px] font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
        Severity Distribution
      </h2>
      <p className="text-[11px] mb-4" style={{ color: 'var(--text-tertiary)' }}>
        Open findings by severity
      </p>

      {total === 0 ? (
        <EmptyState
          icon={<ShieldAlert size={18} />}
          title="No findings"
          description="Severity breakdown will appear after analysis."
          className="py-8"
        />
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={70}
              paddingAngle={3}
              dataKey="value"
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                borderRadius: 6,
                fontSize: 12,
                color: 'var(--text-primary)',
              }}
            />
            <Legend
              iconSize={8}
              iconType="circle"
              wrapperStyle={{ fontSize: 11, color: 'var(--text-secondary)' }}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
