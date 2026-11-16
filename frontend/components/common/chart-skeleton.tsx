import React from 'react';

interface ChartSkeletonProps {
  title?: string;
  height?: number;
}

export function ChartSkeleton({ title, height = 180 }: ChartSkeletonProps) {
  return (
    <div className="card animate-pulse">
      <div className="mb-4">
        {title ? (
          <h3 className="text-xs font-semibold text-zinc-400 mb-1">{title}</h3>
        ) : (
          <div className="h-4 w-32 rounded bg-white/5 mb-1.5" />
        )}
        <div className="h-3 w-48 rounded bg-white/5" />
      </div>
      <div
        className="w-full rounded flex items-end gap-2 p-2 border border-white/5"
        style={{ height, background: 'rgba(255, 255, 255, 0.02)' }}
      >
        <div className="h-1/3 flex-1 rounded-t bg-white/5" />
        <div className="h-1/2 flex-1 rounded-t bg-white/5" />
        <div className="h-2/3 flex-1 rounded-t bg-white/5" />
        <div className="h-4/5 flex-1 rounded-t bg-white/5" />
        <div className="h-1/2 flex-1 rounded-t bg-white/5" />
        <div className="h-3/4 flex-1 rounded-t bg-white/5" />
        <div className="h-full flex-1 rounded-t bg-white/5" />
      </div>
    </div>
  );
}
