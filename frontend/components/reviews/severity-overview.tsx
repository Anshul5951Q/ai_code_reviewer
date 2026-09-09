'use client';

import { ShieldAlert, AlertTriangle, AlertCircle, Info, ShieldCheck } from 'lucide-react';
import type { Finding } from '@/types/security';

interface SeverityOverviewProps {
  findings: Finding[];
  selectedSeverity: string | null;
  onSelectSeverity: (sev: string | null) => void;
}

export function SeverityOverview({
  findings,
  selectedSeverity,
  onSelectSeverity,
}: SeverityOverviewProps) {
  const counts = {
    critical: findings.filter((f) => f.severity === 'critical').length,
    high: findings.filter((f) => f.severity === 'high').length,
    medium: findings.filter((f) => f.severity === 'medium').length,
    low: findings.filter((f) => f.severity === 'low').length,
    info: findings.filter((f) => f.severity === 'info').length,
  };

  const items = [
    {
      id: 'critical',
      label: 'Critical',
      count: counts.critical,
      color: 'text-red-400',
      activeBg: 'bg-red-500/20 border-red-500/50',
      inactiveBg: 'bg-red-500/5 border-red-500/20 hover:bg-red-500/10',
      icon: <ShieldAlert size={14} />,
    },
    {
      id: 'high',
      label: 'High',
      count: counts.high,
      color: 'text-orange-400',
      activeBg: 'bg-orange-500/20 border-orange-500/50',
      inactiveBg: 'bg-orange-500/5 border-orange-500/20 hover:bg-orange-500/10',
      icon: <AlertTriangle size={14} />,
    },
    {
      id: 'medium',
      label: 'Medium',
      count: counts.medium,
      color: 'text-amber-400',
      activeBg: 'bg-amber-500/20 border-amber-500/50',
      inactiveBg: 'bg-amber-500/5 border-amber-500/20 hover:bg-amber-500/10',
      icon: <AlertCircle size={14} />,
    },
    {
      id: 'low',
      label: 'Low',
      count: counts.low,
      color: 'text-blue-400',
      activeBg: 'bg-blue-500/20 border-blue-500/50',
      inactiveBg: 'bg-blue-500/5 border-blue-500/20 hover:bg-blue-500/10',
      icon: <Info size={14} />,
    },
    {
      id: 'info',
      label: 'Info',
      count: counts.info,
      color: 'text-slate-400',
      activeBg: 'bg-slate-500/20 border-slate-500/50',
      inactiveBg: 'bg-slate-500/5 border-slate-500/20 hover:bg-slate-500/10',
      icon: <ShieldCheck size={14} />,
    },
  ];

  return (
    <div className="flex flex-wrap items-center gap-2 mb-4">
      <button
        onClick={() => onSelectSeverity(null)}
        className={`px-3 py-1.5 rounded-md text-xs font-mono transition-all border ${
          selectedSeverity === null
            ? 'bg-white/10 border-white/30 text-[var(--text-primary)]'
            : 'bg-transparent border-[var(--border-subtle)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
        }`}
      >
        All ({findings.length})
      </button>

      {items.map((item) => (
        <button
          key={item.id}
          onClick={() =>
            onSelectSeverity(selectedSeverity === item.id ? null : item.id)
          }
          className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-all border ${
            selectedSeverity === item.id ? item.activeBg : item.inactiveBg
          }`}
        >
          <span className={item.color}>{item.icon}</span>
          <span className={item.color}>{item.count}</span>
          <span className="text-[var(--text-secondary)]">{item.label}</span>
        </button>
      ))}
    </div>
  );
}
