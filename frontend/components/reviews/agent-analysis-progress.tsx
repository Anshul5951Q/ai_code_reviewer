'use client';

import { CheckCircle2, Circle, AlertCircle, Loader2, Sparkles, Shield, Eye, Layers } from 'lucide-react';
import type { AgentRun } from '@/types/agent';

interface AgentAnalysisProgressProps {
  agents: AgentRun[];
  isAnalysisRunning: boolean;
  onTriggerAnalysis?: () => void;
  canTriggerAnalysis?: boolean;
}

interface StageInfo {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
}

const PHASES: StageInfo[] = [
  {
    id: 'ingestion',
    name: 'Repository Ingestion',
    description: 'Clone repository tree and ingest raw source files',
    icon: <Layers size={14} />,
  },
  {
    id: 'intelligence',
    name: 'Repository Intelligence',
    description: 'Deterministic language detection and dependency analysis',
    icon: <Layers size={14} />,
  },
  {
    id: 'code_understanding',
    name: 'Code Understanding',
    description: 'Architectural reasoning, module mapping, and entry points',
    icon: <Eye size={14} />,
  },
  {
    id: 'code_review',
    name: 'Code Review',
    description: 'Code smells, maintainability, and structural quality',
    icon: <Sparkles size={14} />,
  },
  {
    id: 'security_analysis',
    name: 'Security Analysis',
    description: 'Hybrid static rules + LLM reasoning over suspicious patterns',
    icon: <Shield size={14} />,
  },
  {
    id: 'finding_normalization',
    name: 'Finding Normalization & Deduplication',
    description: 'Canonical schema normalization, similarity dedup & scoring',
    icon: <Sparkles size={14} />,
  },
  {
    id: 'verification',
    name: 'Finding Verification',
    description: 'Remediation verification and automated testing (Phase 6)',
    icon: <CheckCircle2 size={14} />,
  },
];

export function AgentAnalysisProgress({
  agents,
  isAnalysisRunning,
  onTriggerAnalysis,
  canTriggerAnalysis,
}: AgentAnalysisProgressProps) {
  // Map agent type to status
  const agentMap = new Map(agents.map((a) => [a.agent_type, a]));

  const getStageStatus = (stageId: string): 'completed' | 'running' | 'failed' | 'queued' | 'pending_phase' => {
    if (stageId === 'ingestion' || stageId === 'intelligence') {
      return 'completed'; // Pre-requisites completed before Phase 5
    }

    if (stageId === 'verification') {
      return 'pending_phase';
    }

    if (stageId === 'finding_normalization') {
      // Normalization is completed when all active agents are completed
      const activeAgents = agents.filter(a => a.agent_type !== 'security_static');
      if (activeAgents.length > 0 && activeAgents.every(a => a.status === 'completed')) {
        return 'completed';
      }
      if (isAnalysisRunning) {
        return 'queued';
      }
      return 'queued';
    }

    if (stageId === 'security_analysis') {
      const secAgent = agentMap.get('security_agent');
      const staticAgent = agentMap.get('security_static');
      if (secAgent?.status === 'completed' || (staticAgent?.status === 'completed' && !secAgent)) {
        return 'completed';
      }
      if (secAgent?.status === 'failed') return 'failed';
      if (secAgent?.status === 'running' || staticAgent?.status === 'running') return 'running';
      if (isAnalysisRunning) return 'running';
      return 'queued';
    }

    const agent = agentMap.get(stageId);
    if (!agent) {
      return isAnalysisRunning ? 'running' : 'queued';
    }
    return agent.status;
  };

  return (
    <div className="card p-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-[14px] font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <Sparkles size={16} className="text-emerald-400" />
            AI Multi-Agent Analysis Pipeline
          </h3>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
            Specialized autonomous agents performing bounded code intelligence, quality review, and vulnerability detection.
          </p>
        </div>

        {canTriggerAnalysis && !isAnalysisRunning && (
          <button
            onClick={onTriggerAnalysis}
            className="btn btn-primary text-xs flex items-center gap-1.5 py-1.5 px-3"
          >
            <Sparkles size={14} />
            Run Multi-Agent Review
          </button>
        )}
      </div>

      <div className="space-y-3">
        {PHASES.map((phase) => {
          const status = getStageStatus(phase.id);

          return (
            <div
              key={phase.id}
              className={`flex items-start justify-between p-3 rounded-md transition-all border ${
                status === 'completed'
                  ? 'bg-emerald-500/5 border-emerald-500/20'
                  : status === 'running'
                  ? 'bg-blue-500/5 border-blue-500/30'
                  : status === 'failed'
                  ? 'bg-red-500/5 border-red-500/30'
                  : 'bg-[var(--bg-card)] border-[var(--border-subtle)] opacity-75'
              }`}
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5">
                  {status === 'completed' && (
                    <CheckCircle2 size={16} className="text-emerald-400" />
                  )}
                  {status === 'running' && (
                    <Loader2 size={16} className="text-blue-400 animate-spin" />
                  )}
                  {status === 'failed' && (
                    <AlertCircle size={16} className="text-red-400" />
                  )}
                  {status === 'queued' && (
                    <Circle size={16} className="text-[var(--text-tertiary)]" />
                  )}
                  {status === 'pending_phase' && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-elevated)] text-[var(--text-tertiary)] font-mono">
                      PHASE 6
                    </span>
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-medium" style={{ color: 'var(--text-primary)' }}>
                      {phase.name}
                    </span>
                  </div>
                  <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                    {phase.description}
                  </p>
                </div>
              </div>

              <div>
                <span
                  className={`text-[11px] font-mono px-2 py-0.5 rounded-full capitalize ${
                    status === 'completed'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : status === 'running'
                      ? 'bg-blue-500/10 text-blue-400'
                      : status === 'failed'
                      ? 'bg-red-500/10 text-red-400'
                      : status === 'pending_phase'
                      ? 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]'
                      : 'text-[var(--text-tertiary)]'
                  }`}
                >
                  {status === 'pending_phase' ? 'Deferred' : status}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
