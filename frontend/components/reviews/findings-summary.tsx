'use client';

import { Shield, Sparkles, Layers, FileCode } from 'lucide-react';
import type { Finding } from '@/types/security';

interface FindingsSummaryProps {
  findings: Finding[];
}

export function FindingsSummary({ findings }: FindingsSummaryProps) {
  const total = findings.length;
  if (total === 0) return null;

  const securityCount = findings.filter((f) => f.category === 'security').length;
  const qualityCount = findings.filter((f) => f.category === 'quality' || f.category === 'maintainability').length;
  const architectureCount = findings.filter((f) => f.category === 'architecture').length;
  const otherCount = total - securityCount - qualityCount - architectureCount;

  const categories = [
    {
      label: 'Security Vulnerabilities',
      count: securityCount,
      icon: <Shield size={14} className="text-red-400" />,
      color: 'bg-red-400',
      pct: total > 0 ? (securityCount / total) * 100 : 0,
    },
    {
      label: 'Code Quality & Maintainability',
      count: qualityCount,
      icon: <Sparkles size={14} className="text-amber-400" />,
      color: 'bg-amber-400',
      pct: total > 0 ? (qualityCount / total) * 100 : 0,
    },
    {
      label: 'Architecture & Design',
      count: architectureCount,
      icon: <Layers size={14} className="text-sky-400" />,
      color: 'bg-sky-400',
      pct: total > 0 ? (architectureCount / total) * 100 : 0,
    },
    ...(otherCount > 0
      ? [
          {
            label: 'Other Issues',
            count: otherCount,
            icon: <FileCode size={14} className="text-slate-400" />,
            color: 'bg-slate-400',
            pct: (otherCount / total) * 100,
          },
        ]
      : []),
  ];

  return (
    <div className="card p-4 mb-5 border border-[var(--border-subtle)]">
      <h4 className="text-[12px] font-semibold text-[var(--text-secondary)] mb-3 uppercase tracking-wider">
        Category Distribution
      </h4>

      {/* Progress bar */}
      <div className="w-full h-2 rounded-full overflow-hidden bg-white/5 flex mb-3">
        {categories.map((c, i) => (
          <div
            key={i}
            style={{ width: `${c.pct}%` }}
            className={`h-full ${c.color}`}
            title={`${c.label}: ${c.count}`}
          />
        ))}
      </div>

      {/* Badges */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        {categories.map((c, i) => (
          <div key={i} className="flex items-center justify-between p-2 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs">
            <div className="flex items-center gap-1.5 truncate">
              {c.icon}
              <span className="truncate text-[var(--text-secondary)]">{c.label}</span>
            </div>
            <span className="font-mono font-bold text-[var(--text-primary)] shrink-0 ml-2">
              {c.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
