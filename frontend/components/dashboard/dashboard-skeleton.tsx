import React from 'react';
import { PageHeader } from '@/components/layout/page-header';
import { ChartSkeleton } from '@/components/common/chart-skeleton';

export function DashboardSkeleton() {
  return (
    <div className="animate-pulse">
      <PageHeader
        title="Dashboard"
        description="Monitor the quality, security, and health of your repositories."
      />

      {/* Skeleton Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="card flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="h-3 w-20 rounded bg-white/5" />
              <div className="w-7 h-7 rounded bg-white/5" />
            </div>
            <div className="h-7 w-16 rounded bg-white/5" />
            <div className="h-3 w-24 rounded bg-white/5" />
          </div>
        ))}
      </div>

      {/* Skeleton Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-6">
        <ChartSkeleton height={160} />
        <ChartSkeleton height={160} />
      </div>

      {/* Skeleton Lower Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-6">
        <div className="card h-64 flex flex-col gap-3">
          <div className="h-4 w-32 rounded bg-white/5 mb-2" />
          <div className="h-10 w-full rounded bg-white/5" />
          <div className="h-10 w-full rounded bg-white/5" />
          <div className="h-10 w-full rounded bg-white/5" />
        </div>
        <div className="card h-64 flex flex-col gap-3">
          <div className="h-4 w-32 rounded bg-white/5 mb-2" />
          <div className="h-10 w-full rounded bg-white/5" />
          <div className="h-10 w-full rounded bg-white/5" />
          <div className="h-10 w-full rounded bg-white/5" />
        </div>
      </div>
    </div>
  );
}

