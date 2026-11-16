'use client';

import { memo } from 'react';
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
  code_quality: {
    label: 'Code Quality Agent',
    description: 'AST cyclomatic complexity, code smells, duplication & maintainability',
    icon: <Sparkles size={16} />,
    color: 'text-violet-400',
  },
  code_review: {
    label: 'Code Quality Agent',
    description: 'AST cyclomatic complexity, code smells, duplication & maintainability',
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
    label: 'Security Detection Agent',
    description: 'Source -> Transformation -> Sink exploitability analysis & CWE mapping',
    icon: <Shield size={16} />,
    color: 'text-emerald-400',
  },
  finding_correlator: {
    label: 'Finding Correlator',
    description: 'Cross-agent correlation, cluster deduplication & unified findings',
    icon: <Sparkles size={16} />,
    color: 'text-pink-400',
  },
  remediation: {
    label: 'Remediation Agent (Gate 4)',
    description: 'Automated patch generation, isolated workspace & AST verification',
    icon: <Sparkles size={16} />,
    color: 'text-amber-400',
  },
  verification: {
    label: 'Verification Agent (Gate 5)',
    description: 'Independent verification & deterministic decision engine',
    icon: <Shield size={16} />,
    color: 'text-cyan-400',
  },
};

export const AgentStatusCard = memo(function AgentStatusCard({ agent }: AgentStatusCardProps) {
  const meta = AGENT_META[agent.agent_type] || {
    label: agent.agent_type.replace(/_/g, ' '),
    description: 'Specialized analysis agent',
    icon: <Sparkles size={16} />,
    color: 'text-indigo-400',
  };

  const durationSec = agent.duration_ms
    ? (agent.duration_ms / 1000).toFixed(1) + 's'
    : '—';

  let displayStatus = agent.status as string;
  let statusColorClass = 'text-[var(--text-tertiary)]';

  let extraMetaInfo: string | null = null;

  if (agent.agent_type === 'code_understanding') {
    if (agent.status === 'running' || agent.status === 'analyzing') {
      displayStatus = 'Analyzing';
      statusColorClass = 'bg-blue-500/10 text-blue-400';
    } else if (agent.status === 'verifying') {
      displayStatus = 'Verifying Gate 1';
      statusColorClass = 'bg-amber-500/10 text-amber-400';
    } else if (agent.status === 'completed' || agent.status === 'verified') {
      let isVerified = agent.status === 'verified';
      let isFailedValidation = false;
      if (agent.metadata_json) {
        try {
          const metaParsed = JSON.parse(agent.metadata_json);
          const vStatus = metaParsed.verification_status || metaParsed.gate_1?.status;
          if (vStatus === 'verified' || vStatus === 'verified_with_scrubbing') {
            isVerified = true;
          } else if (vStatus === 'failed_validation') {
            isFailedValidation = true;
          }
        } catch {
          // ignore
        }
      }
      if (isVerified) {
        displayStatus = 'Gate 1 Verified';
        statusColorClass = 'bg-emerald-500/10 text-emerald-400';
      } else if (isFailedValidation) {
        displayStatus = 'Failed Gate 1';
        statusColorClass = 'bg-red-500/10 text-red-400';
      } else {
        displayStatus = 'Unverified';
        statusColorClass = 'bg-amber-500/10 text-amber-400';
      }
    } else if (agent.status === 'failed') {
      displayStatus = 'Failed';
      statusColorClass = 'bg-red-500/10 text-red-400';
    }
  } else if (agent.agent_type === 'code_quality' || agent.agent_type === 'code_review') {
    if (agent.status === 'running') {
      displayStatus = 'Running';
      statusColorClass = 'bg-blue-500/10 text-blue-400';
    } else if (agent.status === 'completed') {
      let gateStatus = 'completed';
      if (agent.metadata_json) {
        try {
          const parsed = JSON.parse(agent.metadata_json);
          const g2 = parsed.gate_2;
          if (g2?.status === 'verified') {
            gateStatus = 'Gate 2 Verified';
            statusColorClass = 'bg-emerald-500/10 text-emerald-400';
          } else if (g2?.status === 'verified_with_scrubbing') {
            gateStatus = 'Verified (Scrubbed)';
            statusColorClass = 'bg-emerald-500/10 text-emerald-400';
          } else if (g2?.status === 'failed_validation' || g2?.status === 'rejected') {
            gateStatus = 'Failed Gate 2';
            statusColorClass = 'bg-red-500/10 text-red-400';
          } else {
            statusColorClass = 'bg-emerald-500/10 text-emerald-400';
          }
          if (g2?.rejected_count > 0) {
            extraMetaInfo = `${g2.rejected_count} rejected by Gate 2`;
          }
        } catch {
          statusColorClass = 'bg-emerald-500/10 text-emerald-400';
        }
      }
      displayStatus = gateStatus;
    } else if (agent.status === 'failed') {
      displayStatus = 'Failed';
      statusColorClass = 'bg-red-500/10 text-red-400';
    }
  } else if (agent.agent_type === 'security_agent') {
    if (agent.status === 'running') {
      displayStatus = 'Running';
      statusColorClass = 'bg-blue-500/10 text-blue-400';
    } else if (agent.status === 'completed') {
      let gateStatus = 'completed';
      if (agent.metadata_json) {
        try {
          const parsed = JSON.parse(agent.metadata_json);
          const g3 = parsed.gate_3;
          if (g3?.status === 'verified') {
            gateStatus = 'Gate 3 Verified';
            statusColorClass = 'bg-emerald-500/10 text-emerald-400';
          } else if (g3?.status === 'verified_with_scrubbing') {
            gateStatus = 'Verified (Scrubbed)';
            statusColorClass = 'bg-emerald-500/10 text-emerald-400';
          } else if (g3?.status === 'failed_validation' || g3?.status === 'rejected') {
            gateStatus = 'Failed Gate 3';
            statusColorClass = 'bg-red-500/10 text-red-400';
          } else {
            statusColorClass = 'bg-emerald-500/10 text-emerald-400';
          }
          if (g3?.rejected_count > 0) {
            extraMetaInfo = `${g3.rejected_count} rejected by Gate 3`;
          }
        } catch {
          statusColorClass = 'bg-emerald-500/10 text-emerald-400';
        }
      }
      displayStatus = gateStatus;
    } else if (agent.status === 'failed') {
      displayStatus = 'Failed';
      statusColorClass = 'bg-red-500/10 text-red-400';
    }
  } else {
    if (agent.status === 'completed') {
      statusColorClass = 'bg-emerald-500/10 text-emerald-400';
    } else if (agent.status === 'running') {
      statusColorClass = 'bg-blue-500/10 text-blue-400';
    } else if (agent.status === 'failed') {
      statusColorClass = 'bg-red-500/10 text-red-400';
    }
  }

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
            className={`text-[10px] font-mono px-2 py-0.5 rounded-full capitalize ${statusColorClass}`}
          >
            {displayStatus}
          </span>
        </div>


        <p className="text-[11px] mb-3 leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
          {meta.description}
        </p>

        {extraMetaInfo && (
          <div className="text-[10px] text-amber-400 font-mono mb-2 px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 inline-block">
            {extraMetaInfo}
          </div>
        )}

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
});
