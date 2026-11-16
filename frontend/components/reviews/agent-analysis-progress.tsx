'use client';

import { CheckCircle2, Circle, AlertCircle, Loader2, Sparkles, Shield, Eye, Layers, Wrench, ShieldCheck } from 'lucide-react';
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
    name: 'Code Understanding (Gate 1)',
    description: 'Architecture synthesis, entry points & AST-verified symbols',
    icon: <Eye size={14} />,
  },
  {
    id: 'code_quality',
    name: 'Code Quality Analysis (Gate 2)',
    description: 'AST cyclomatic complexity, code smells, duplication & Gate 2 verification',
    icon: <Sparkles size={14} />,
  },
  {
    id: 'security_analysis',
    name: 'Security Detection (Gate 3)',
    description: 'Deterministic security scan + exploitability reasoning & Gate 3 verification',
    icon: <Shield size={14} />,
  },
  {
    id: 'finding_normalization',
    name: 'Finding Correlation & Intelligence',
    description: 'Cross-agent correlation, cluster deduplication & deterministic scoring',
    icon: <Sparkles size={14} />,
  },
  {
    id: 'remediation',
    name: 'Remediation & Patch Generation (Gate 4)',
    description: 'Automated remediation, AST patch validation & syntax safety',
    icon: <Wrench size={14} />,
  },
  {
    id: 'verification',
    name: 'Independent Verification (Gate 5)',
    description: 'Deterministic re-scan, verification agent & Gate 5 decision engine',
    icon: <ShieldCheck size={14} />,
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

  const getStageMeta = (stageId: string): {
    status: 'completed' | 'verified' | 'verifying' | 'running' | 'failed' | 'queued' | 'skipped';
    badgeText: string;
    details?: string;
  } => {
    if (stageId === 'ingestion' || stageId === 'intelligence') {
      return { status: 'completed', badgeText: 'Completed' };
    }

    if (stageId === 'code_understanding') {
      const agent = agentMap.get('code_understanding');
      if (!agent) {
        return { status: isAnalysisRunning ? 'running' : 'queued', badgeText: isAnalysisRunning ? 'Analyzing' : 'Queued' };
      }
      if (agent.status === 'running' || agent.status === 'analyzing') {
        return { status: 'running', badgeText: 'Analyzing' };
      }
      if (agent.status === 'verifying') {
        return { status: 'verifying', badgeText: 'Verifying Gate 1' };
      }
      if (agent.status === 'completed' || agent.status === 'verified') {
        let isVerified = agent.status === 'verified';
        if (agent.metadata_json) {
          try {
            const parsed = JSON.parse(agent.metadata_json);
            const v = parsed.verification_status || parsed.gate_1?.status;
            if (v === 'verified' || v === 'verified_with_scrubbing') {
              isVerified = true;
            }
          } catch {
            // ignore
          }
        }
        return {
          status: isVerified ? 'verified' : 'completed',
          badgeText: isVerified ? 'Gate 1 Verified' : 'Completed',
          details: agent.duration_ms ? `${(agent.duration_ms / 1000).toFixed(1)}s` : undefined,
        };
      }
      if (agent.status === 'failed') {
        return { status: 'failed', badgeText: 'Failed', details: agent.error || 'Gate 1 failed' };
      }
      return { status: 'queued', badgeText: 'Queued' };
    }

    if (stageId === 'code_quality' || stageId === 'code_review') {
      const qAgent = agentMap.get('code_quality') || agentMap.get('code_review');
      const underAgent = agentMap.get('code_understanding');
      if (!qAgent) {
        const isQueued = !underAgent || underAgent.status !== 'completed';
        return {
          status: isAnalysisRunning && !isQueued ? 'running' : 'queued',
          badgeText: isAnalysisRunning && !isQueued ? 'Analyzing' : 'Queued',
        };
      }
      if (qAgent.status === 'running') return { status: 'running', badgeText: 'Analyzing' };
      if (qAgent.status === 'completed' || qAgent.status === 'verified') {
        let isVerified = qAgent.status === 'verified';
        if (qAgent.metadata_json) {
          try {
            const parsed = JSON.parse(qAgent.metadata_json);
            const g2 = parsed.gate_2;
            if (g2?.status === 'verified' || g2?.status === 'verified_with_scrubbing') {
              isVerified = true;
            }
          } catch {
            // ignore
          }
        }
        return {
          status: isVerified ? 'verified' : 'completed',
          badgeText: isVerified ? 'Gate 2 Verified' : 'Completed',
          details: `${qAgent.findings_generated} findings${qAgent.duration_ms ? ` • ${(qAgent.duration_ms / 1000).toFixed(1)}s` : ''}`,
        };
      }
      if (qAgent.status === 'failed') {
        return { status: 'failed', badgeText: 'Failed', details: qAgent.error || 'Quality analysis failed' };
      }
      return { status: 'queued', badgeText: 'Queued' };
    }

    if (stageId === 'security_analysis') {
      const secAgent = agentMap.get('security_agent');
      const staticAgent = agentMap.get('security_static');

      // Security Detection is only completed when the dedicated security_agent runs or if static is finished and no security_agent is needed
      if (secAgent) {
        if (secAgent.status === 'completed' || secAgent.status === 'verified') {
          let isVerified = secAgent.status === 'verified';
          if (secAgent.metadata_json) {
            try {
              const parsed = JSON.parse(secAgent.metadata_json);
              const g3 = parsed.gate_3;
              if (g3?.status === 'verified' || g3?.status === 'verified_with_scrubbing') {
                isVerified = true;
              }
            } catch {
              // ignore
            }
          }
          const totalFindings = secAgent.findings_generated;
          return {
            status: isVerified ? 'verified' : 'completed',
            badgeText: isVerified ? 'Gate 3 Verified' : 'Completed',
            details: `${totalFindings} findings${secAgent.duration_ms ? ` • ${(secAgent.duration_ms / 1000).toFixed(1)}s` : ''}`,
          };
        }
        if (secAgent.status === 'running') return { status: 'running', badgeText: 'Analyzing' };
        if (secAgent.status === 'failed') {
          return { status: 'failed', badgeText: 'Failed', details: secAgent.error || 'Security analysis failed' };
        }
      }

      // If only static has run so far and analysis is currently active, security LLM agent is still queued/analyzing
      if (staticAgent?.status === 'completed' && isAnalysisRunning) {
        return {
          status: 'running',
          badgeText: 'Analyzing',
          details: `${staticAgent.findings_generated} static findings found`,
        };
      }
      if (staticAgent?.status === 'completed' && !isAnalysisRunning) {
        return {
          status: 'completed',
          badgeText: 'Completed',
          details: `${staticAgent.findings_generated} static findings`,
        };
      }
      return { status: isAnalysisRunning ? 'running' : 'queued', badgeText: isAnalysisRunning ? 'Analyzing' : 'Queued' };
    }

    if (stageId === 'finding_normalization') {
      const corrAgent = agentMap.get('finding_correlator') || agentMap.get('correlator');
      if (corrAgent && (corrAgent.status === 'completed' || corrAgent.status === 'verified')) {
        return {
          status: 'completed',
          badgeText: 'Correlated',
          details: `${corrAgent.findings_generated} clusters unified`,
        };
      }
      if (corrAgent?.status === 'running') return { status: 'running', badgeText: 'Correlating' };
      if (corrAgent?.status === 'failed') return { status: 'failed', badgeText: 'Failed' };
      return { status: 'queued', badgeText: 'Queued' };
    }

    if (stageId === 'remediation') {
      const remAgent = agentMap.get('remediation') || agentMap.get('remediation_agent');
      if (remAgent && (remAgent.status === 'completed' || remAgent.status === 'verified')) {
        return {
          status: 'verified',
          badgeText: 'Gate 4 Validated',
          details: `${remAgent.findings_generated} patches generated`,
        };
      }
      if (remAgent?.status === 'running') return { status: 'running', badgeText: 'Generating' };
      if (remAgent?.status === 'failed') return { status: 'failed', badgeText: 'Failed' };
      return { status: 'queued', badgeText: 'Ready' };
    }

    if (stageId === 'verification') {
      const verAgent = agentMap.get('verification') || agentMap.get('verification_agent');
      if (verAgent && (verAgent.status === 'completed' || verAgent.status === 'verified')) {
        return {
          status: 'verified',
          badgeText: 'Gate 5 Decision Verified',
          details: `${verAgent.findings_generated} verified`,
        };
      }
      if (verAgent?.status === 'running') return { status: 'running', badgeText: 'Verifying' };
      if (verAgent?.status === 'failed') return { status: 'failed', badgeText: 'Failed' };
      return { status: 'queued', badgeText: 'Ready' };
    }

    return { status: 'queued', badgeText: 'Queued' };
  };

  return (
    <div className="card p-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-[14px] font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <Sparkles size={16} className="text-emerald-400" />
            AI Multi-Agent Analysis Pipeline & Five Verification Gates
          </h3>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
            Autonomous specialized agents with deterministic verification gates, exploitability reasoning, and automated patch validation.
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
          const { status, badgeText, details } = getStageMeta(phase.id);

          return (
            <div
              key={phase.id}
              className={`flex items-start justify-between p-3 rounded-md transition-all border ${
                status === 'completed' || status === 'verified'
                  ? 'bg-emerald-500/5 border-emerald-500/20'
                  : status === 'running'
                  ? 'bg-blue-500/5 border-blue-500/30'
                  : status === 'verifying'
                  ? 'bg-amber-500/5 border-amber-500/30'
                  : status === 'failed'
                  ? 'bg-red-500/5 border-red-500/30'
                  : 'bg-[var(--bg-card)] border-[var(--border-subtle)] opacity-75'
              }`}
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5">
                  {(status === 'completed' || status === 'verified') && (
                    <CheckCircle2 size={16} className="text-emerald-400" />
                  )}
                  {status === 'running' && (
                    <Loader2 size={16} className="text-blue-400 animate-spin" />
                  )}
                  {status === 'verifying' && (
                    <Loader2 size={16} className="text-amber-400 animate-spin" />
                  )}
                  {status === 'failed' && (
                    <AlertCircle size={16} className="text-red-400" />
                  )}
                  {status === 'queued' && (
                    <Circle size={16} className="text-[var(--text-tertiary)]" />
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-medium" style={{ color: 'var(--text-primary)' }}>
                      {phase.name}
                    </span>
                    {details && (
                      <span className="text-[11px] font-mono text-[var(--text-tertiary)]">
                        ({details})
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                    {phase.description}
                  </p>
                </div>
              </div>

              <div>
                <span
                  className={`text-[11px] font-mono px-2 py-0.5 rounded-full capitalize ${
                    status === 'completed' || status === 'verified'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : status === 'running'
                      ? 'bg-blue-500/10 text-blue-400'
                      : status === 'verifying'
                      ? 'bg-amber-500/10 text-amber-400'
                      : status === 'failed'
                      ? 'bg-red-500/10 text-red-400'
                      : 'text-[var(--text-tertiary)]'
                  }`}
                >
                  {badgeText}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
