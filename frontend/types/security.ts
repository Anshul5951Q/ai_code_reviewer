export type { ReviewStatus } from './review';
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type FindingStatus =
  | 'open'
  | 'resolved'
  | 'ignored'
  | 'false_positive'
  | 'remediation_available'
  | 'remediation_in_progress'
  | 'verification_pending'
  | 'verification_failed'
  | 'remediation_exhausted';
export type FindingCategory =
  | 'security'
  | 'quality'
  | 'maintainability'
  | 'architecture'
  | 'style'
  | 'performance'
  | 'dependency';

export interface Finding {
  id: string;
  review_id: string;
  category: FindingCategory;
  severity: Severity;
  title: string;
  description: string | null;
  file_path: string | null;
  line_number: number | null;
  start_line?: number | null;
  end_line?: number | null;
  type?: string | null;
  evidence?: string | null;
  cwe?: string | null;
  source?: string | null;
  confidence: number | null;
  status: FindingStatus;
  created_at: string;
}

export interface FindingListResponse {
  items: Finding[];
  total: number;
}

export interface SecuritySummary {
  overall_score: number | null;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  resolved_count: number;
  open_count: number;
  repositories_analyzed: number;
  remediation_runs_count?: number;
  verification_success_rate?: number | null;
}

export type RelationshipType =
  | 'exact_duplicate'
  | 'overlapping'
  | 'shared_root_cause'
  | 'related'
  | 'independent';

export interface FindingRelationship {
  id: string;
  correlated_finding_id: string;
  source_finding_id: string;
  relationship_type: RelationshipType;
  confidence: number;
  rationale?: string | null;
  created_at: string;
  source_finding?: Finding | null;
}

export interface CorrelatedFinding {
  id: string;
  review_id: string;
  snapshot_id?: string | null;
  primary_finding_id: string;
  category: FindingCategory;
  severity: Severity;
  title: string;
  description?: string | null;
  root_cause?: string | null;
  file_path?: string | null;
  line_number?: number | null;
  start_line?: number | null;
  end_line?: number | null;
  confidence?: number | null;
  evidence?: string | null;
  cwe?: string | null;
  correlation_score: number;
  correlation_explanation?: string | null;
  correlation_version: string;
  status: FindingStatus;
  created_at: string;
  relationships: FindingRelationship[];
}

export interface CorrelatedFindingListResponse {
  items: CorrelatedFinding[];
  total: number;
}

export interface CorrelationStatus {
  review_id: string;
  status: string;
  total_raw_findings: number;
  correlated_clusters_count: number;
  exact_duplicates_count: number;
  overlapping_count: number;
  shared_root_cause_count: number;
  independent_count: number;
  semantic_evaluated: boolean;
  correlation_version: string;
}


