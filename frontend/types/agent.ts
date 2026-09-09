export type AgentType =
  | 'code_understanding'
  | 'code_review'
  | 'security_static'
  | 'security_agent';

export type AgentStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface AgentRun {
  id: string;
  review_id: string;
  agent_type: string;
  type?: string;
  status: AgentStatus;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  files_analyzed: number;
  findings_generated: number;
  error?: string | null;
  metadata_json?: string | null;
}

export interface AgentRunListResponse {
  agents: AgentRun[];
}

export interface StartPhase5AnalysisResponse {
  review_id: string;
  status: string;
  message: string;
}
