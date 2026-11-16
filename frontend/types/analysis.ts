// Analysis job and repository snapshot types for Phase 3

export type AnalysisStage =
  | 'repository_fetch'
  | 'file_filtering'
  | 'content_fetch'
  | 'language_detection'
  | 'dependency_analysis'
  | 'repository_intelligence'
  | 'snapshot_creation'
  | 'understanding'
  | 'verifying_understanding'
  | 'quality_analysis'
  | 'security_analysis'
  | 'verifying_findings'
  | 'correlating'
  | 'completed';

export type AnalysisJobStatus =
  | 'queued'
  | 'ingesting'
  | 'indexing'
  | 'analyzing'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface AnalysisJob {
  id: string;
  review_id: string;
  status: AnalysisJobStatus;
  current_stage: AnalysisStage | null;
  progress: number;
  files_total: number;
  files_processed: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface StartAnalysisResponse {
  job_id: string;
  review_id: string;
  status: AnalysisJobStatus;
  message: string;
}

export interface LanguageStat {
  files: number;
  percentage: number;
}

export interface DependencyInfo {
  name: string;
  version: string | null;
  type: 'dependency' | 'dev_dependency' | 'peer_dependency' | 'optional';
  source_file: string;
}

export interface CoverageMetrics {
  total_discovered: number;
  total_eligible_source: number;
  downloaded_count: number;
  analyzed_count: number;
  coverage_percentage: number;
  coverage_status: string;
  limitations: string[];
}

export interface RepositoryStructure {
  entry_points: string[];
  largest_files: Array<{ path: string; size: number; lines: number }>;
  directory_structure: Record<string, number>;
  total_dependencies: number;
  coverage?: CoverageMetrics;
  file_inventory?: Record<string, unknown>;
}

export interface RepositorySnapshot {
  id: string;
  review_id: string;
  commit_sha: string;
  branch: string;
  total_files: number;
  source_files: number;
  test_files: number;
  config_files: number;
  total_lines: number;
  languages: Record<string, LanguageStat>;
  frameworks: string[];
  dependencies: DependencyInfo[];
  structure: RepositoryStructure | null;
  created_at: string;
}

// Stage display metadata
export const STAGE_LABELS: Record<AnalysisStage, string> = {
  repository_fetch: 'Fetching Repository',
  file_filtering: 'Filtering Files',
  content_fetch: 'Fetching File Contents',
  language_detection: 'Detecting Languages',
  dependency_analysis: 'Analyzing Dependencies',
  repository_intelligence: 'Building Repository Map',
  snapshot_creation: 'Creating Snapshot',
  understanding: 'Code Understanding & Architecture',
  verifying_understanding: 'Gate 1 Verification',
  quality_analysis: 'Code Quality Analysis',
  security_analysis: 'Security Vulnerability Detection',
  verifying_findings: 'Gates 2 & 3 Verification',
  correlating: 'Finding Correlation & Intelligence',
  completed: 'Analysis Complete',
};

export const STAGES_ORDER: AnalysisStage[] = [
  'repository_fetch',
  'file_filtering',
  'content_fetch',
  'language_detection',
  'dependency_analysis',
  'repository_intelligence',
  'snapshot_creation',
  'understanding',
  'verifying_understanding',
  'quality_analysis',
  'security_analysis',
  'verifying_findings',
  'correlating',
  'completed',
];
