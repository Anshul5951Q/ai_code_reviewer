export type RemediationStatus =
  | 'queued'
  | 'generating'
  | 'patch_generated'
  | 'patch_validated'
  | 'verifying'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type VerificationStatus =
  | 'not_started'
  | 'resolved'
  | 'partially_resolved'
  | 'still_vulnerable'
  | 'verification_failed';

export interface CodeChange {
  file_path: string;
  start_line: number;
  end_line: number;
  original_code: string;
  replacement_code: string;
}

export interface RemediationPlan {
  finding_id: string;
  strategy: string;
  explanation: string;
  files_changed: string[];
  changes: CodeChange[];
  unified_diff: string;
  confidence: number;
}

export interface VerificationResult {
  status: VerificationStatus;
  confidence: number;
  reason: string;
  remaining_risk?: string | null;
  new_findings: Array<{
    category?: string;
    severity?: string;
    title?: string;
    description?: string;
  }>;
  evidence: string[];
}

export interface RemediationRun {
  id: string;
  review_id: string;
  finding_id: string;
  status: RemediationStatus;
  agent_type: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  files_modified: number;
  patch_valid: boolean;
  verification_status: VerificationStatus;
  error?: string | null;
  metadata_json?: string | null;
  created_at: string;
}

export interface RemediationResultResponse {
  remediation_id: string;
  finding_id: string;
  strategy: string;
  explanation: string;
  files_changed: string[];
  changes: CodeChange[];
  diff: string;
  verification_status: VerificationStatus;
  remediation_confidence: number;
  verification_confidence: number;
  verification_reason: string;
  remaining_risk?: string | null;
  new_findings: Array<{
    category?: string;
    severity?: string;
    title?: string;
    description?: string;
  }>;
  attempt_number: number;
  created_at: string;
}

export interface RemediationHistoryResponse {
  finding_id: string;
  total_attempts: number;
  can_retry: boolean;
  runs: RemediationRun[];
}
