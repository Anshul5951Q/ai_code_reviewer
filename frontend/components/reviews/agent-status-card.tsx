'use client';

import { CheckCircle, AlertCircle, Clock, FileCode, Search, Shield, Eye, Sparkles } from 'lucide-react';
import type { AgentRun } from '@/types/agent';

interface AgentStatusCardProps {
  agent: AgentRun;
}

const AGENT_META: Record<
  string,
  { label: string; description: string; icon: React.ReactNode; color: string }
> = {
  code_understanding: {
    label: 'Code Understanding',
    description: 'Module boundaries, architecture, entry points & project patterns',
    icon: <Eye size={16} />,
    color: 'text-sky-400',
  },
  code_review: {
    label: 'Code Review Agent',
    description: 'Maintainability smells, complex functions, and code quality',
    icon: <Sparkles size={16} />,
    color: 'text-violet-400',
  },
  security_static: {
    label: 'Static Security Engine',
    description: 'Deterministic rule scanning for SQLi, XSS, secrets & permissions',
    icon: <Search size={16} />,
    color: 'text-amber-400',
  },
  security_agent: {
    label: 'LLM Security Agent',
    description: 'Vulnerability exploitability, attack path verification & CWE mapping',
    icon: <Shield size={16} />,
    color: 'text-emerald-400',
  },
};

export function AgentStatusCard({ agent }: AgentStatusCardProps) {
  const meta = AGENT_META[agent.agent_type] || {
    label: agent.agent_type.replace(/_/g, ' '),
    description: 'Specialized analysis agent',
    icon: <Sparkles size={16} />,
    color: 'text-indigo-400',
  };

  const durationSec = agent.duration_ms
    ? (agent.duration_ms / 1000).toFixed(1) + 's'
    : '—';

  return (
    <div className="card p-4 flex flex-col justify-between border border-[var(--border-subtle)] hover:border-[var(--border-default)] transition-colors">
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className={meta.color}>{meta.icon}</span>
            <span className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
              {meta.label}
            </span>
          </div>

          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded-full capitalize ${
              agent.status === 'completed'
                ? 'bg-emerald-500/10 text-emerald-400'
                : agent.status === 'running'
                ? 'bg-blue-500/10 text-blue-400'
                : agent.status === 'failed'
                ? 'bg-red-500/10 text-red-400'
                : 'text-[var(--text-tertiary)]'
            }`}
          >
            {agent.status}
          </span>
        </div>

        <p className="text-[11px] mb-3 leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
          {meta.description}
        </p>

        {agent.error && (
          <div className="p-2 mb-3 bg-red-500/10 border border-red-500/20 rounded text-[11px] text-red-400 flex items-start gap-1.5">
            <AlertCircle size={13} className="shrink-0 mt-0.5" />
            <span className="break-all">{agent.error}</span>
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-[var(--border-subtle)] grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="flex items-center justify-center gap-1 text-[11px] text-[var(--text-tertiary)] mb-0.5">
            <Clock size={11} />
            Time
          </div>
          <span className="text-[12px] font-mono font-medium" style={{ color: 'var(--text-secondary)' }}>
            {durationSec}
          </span>
        </div>

        <div>
          <div className="flex items-center justify-center gap-1 text-[11px] text-[var(--text-tertiary)] mb-0.5">
            <FileCode size={11} />
            Files
          </div>
          <span className="text-[12px] font-mono font-medium" style={{ color: 'var(--text-secondary)' }}>
            {agent.files_analyzed}
          </span>
        </div>

        <div>
          <div className="flex items-center justify-center gap-1 text-[11px] text-[var(--text-tertiary)] mb-0.5">
            <CheckCircle size={11} />
            Findings
          </div>
          <span className="text-[12px] font-mono font-medium text-emerald-400">
            {agent.findings_generated}
          </span>
        </div>
      </div>
    </div>
  );
}
