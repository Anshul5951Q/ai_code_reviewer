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

export type PatchRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type Gate4Status =
  | 'PENDING'
  | 'VALIDATING'
  | 'PASSED'
  | 'FAILED'
  | 'PARTIALLY_PASSED'
  | 'UNABLE_TO_VERIFY';

export type Gate5Decision =
  | 'RESOLVED'
  | 'UNRESOLVED'
  | 'PARTIALLY_RESOLVED'
  | 'BLOCKED'
  | 'UNABLE_TO_VERIFY';

export type VerificationOutcome =
  | 'FIXED'
  | 'PARTIALLY_FIXED'
  | 'NOT_FIXED'
  | 'REGRESSION_DETECTED'
  | 'UNABLE_TO_VERIFY';

export interface SourceTransformationSinkAssessment {
  source_input?: string | null;
  transformation?: string | null;
  sink?: string | null;
  is_exploitable_path_severed: boolean;
  remaining_attack_surface?: string | null;
  rationale: string;
}

export interface ScannerComparisonResult {
  pre_patch_findings_count: number;
  post_patch_findings_count: number;
  target_defect_cleared: boolean;
  cleared_findings: Array<Record<string, unknown>>;
  retained_findings: Array<Record<string, unknown>>;
  new_findings: Array<Record<string, unknown>>;
}

export interface Gate5DecisionResult {
  decision: Gate5Decision;
  passed_conditions: string[];
  failed_conditions: string[];
  reasons: string[];
  patch_version: number;
  snapshot_id?: string | null;
  is_resolved: boolean;
  limitations?: string | null;
}

export interface VerificationRunResponse {
  id: string;
  review_id: string;
  remediation_run_id: string;
  finding_id?: string | null;
  correlated_finding_id?: string | null;
  snapshot_id?: string | null;
  patch_version: number;
  agent_run_id?: string | null;
  status: string;
  outcome: VerificationOutcome;
  gate_5_decision: Gate5Decision;
  confidence: number;
  methodology: string;
  reason?: string | null;
  source_transformation_sink?: SourceTransformationSinkAssessment | null;
  scanner_comparison?: ScannerComparisonResult | null;
  test_results?: Array<Record<string, unknown>>;
  regression_results?: Array<Record<string, unknown>>;
  remaining_evidence?: string | null;
  new_issues_detected?: Array<Record<string, unknown>>;
  decision_reasons: string[];
  failed_conditions: string[];
  limitations?: string | null;
  duration_ms?: number | null;
  created_at: string;
}

export interface VerificationHistoryResponse {
  remediation_run_id?: string | null;
  finding_id?: string | null;
  total_runs: number;
  runs: VerificationRunResponse[];
}

export interface FindingResolutionStatusResponse {
  finding_id: string;
  review_id: string;
  title: string;
  category: string;
  severity: string;
  finding_status: string;
  is_resolved: boolean;
  latest_remediation_id?: string | null;
  gate_4_status?: Gate4Status | null;
  gate_5_decision?: Gate5Decision | null;
  patch_version?: number | null;
}

export interface CodeChange {
  file_path: string;
  start_line: number;
  end_line: number;
  original_code: string;
  replacement_code: string;
}

export interface Gate4CheckResult {
  check_name: string;
  status: 'passed' | 'failed' | 'warning' | 'skipped';
  details: string;
  evidence?: string | null;
}

export interface Gate4AuditReport {
  gate_status: Gate4Status;
  checks: Gate4CheckResult[];
  syntax_valid: boolean;
  static_finding_cleared: boolean;
  new_issues_detected: Array<Record<string, unknown>>;
  timestamp?: string;
}

export interface PatchRiskAssessment {
  level: PatchRiskLevel;
  score: number;
  factors: string[];
  explanation: string;
}

export interface RemediationPlan {
  finding_id: string;
  strategy: string;
  explanation: string;
  files_changed: string[];
  changes: CodeChange[];
  unified_diff: string;
  confidence: number;
  root_cause?: string | null;
  proposed_solution?: string | null;
  expected_behavior?: string | null;
  potential_side_effects?: string | null;
  required_tests?: string[];
  risk_assessment?: PatchRiskAssessment | null;
  gate_4_status?: Gate4Status;
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
  finding_id?: string | null;
  correlated_finding_id?: string | null;
  snapshot_id?: string | null;
  status: RemediationStatus;
  agent_type: string;
  patch_version: number;
  risk_level: PatchRiskLevel;
  gate_4_status: Gate4Status;
  gate_5_decision?: Gate5Decision | null;
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
  id?: string;
  remediation_id?: string;
  finding_id?: string | null;
  correlated_finding_id?: string | null;
  status: RemediationStatus;
  strategy?: string | null;
  explanation?: string | null;
  changed_files?: string[];
  files_changed?: string[];
  diff: string;
  patch_version?: number;
  risk_level?: PatchRiskLevel;
  risk_assessment?: PatchRiskAssessment | null;
  gate_4_status?: Gate4Status;
  gate_4_checks?: Gate4CheckResult[];
  gate_5_decision?: Gate5Decision | null;
  gate_5_result?: Gate5DecisionResult | null;
  root_cause?: string | null;
  potential_side_effects?: string | null;
  expected_behavior?: string | null;
  verification_status: VerificationStatus;
  confidence?: number | null;
  remediation_confidence?: number | null;
  verification_confidence?: number;
  verification_reason?: string;
  verification_explanation?: string | null;
  remaining_risk?: string | null;
  new_findings?: Array<{
    category?: string;
    severity?: string;
    title?: string;
    description?: string;
  }>;
  attempt_number?: number;
  created_at?: string;
}

export interface RemediationHistoryResponse {
  finding_id?: string | null;
  total_attempts: number;
  can_retry: boolean;
  runs: RemediationRun[];
}

export interface BatchRemediationResponse {
  review_id: string;
  queued_runs: RemediationRun[];
  total_queued: number;
  skipped_count: number;
  skipped_reasons: string[];
}
