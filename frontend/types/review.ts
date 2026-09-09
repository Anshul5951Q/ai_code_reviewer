export type ReviewStatus =
  | 'queued'
  | 'ingesting'
  | 'ready_for_analysis'
  | 'running'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed'
  | 'cancelled';

export interface Review {
  id: string;
  repository_id: string;
  commit_sha: string;
  branch: string;
  status: ReviewStatus;
  overall_score: number | null;
  security_score: number | null;
  quality_score: number | null;
  architecture_score?: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ReviewListResponse {
  items: Review[];
  total: number;
}

export interface ReviewFilters {
  search: string;
  repository: string;
  status: ReviewStatus | 'all';
  severity: string;
  dateFrom: string;
  dateTo: string;
}
