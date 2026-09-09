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

