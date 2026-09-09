export type RepositoryVisibility = 'public' | 'private' | 'internal';

export interface Repository {
  id: string;
  name: string;
  full_name: string;
  owner: string;
  default_branch: string;
  visibility: RepositoryVisibility;
  language: string | null;
  github_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface RepositoryCreate {
  name: string;
  full_name: string;
  owner: string;
  default_branch?: string;
  visibility?: RepositoryVisibility;
  language?: string | null;
  github_id?: number | null;
}

export interface RepositoryListResponse {
  items: Repository[];
  total: number;
}

export interface RepositoryHealth {
  repository: string;
  overall_score: number | null;
  security_score: number | null;
  quality_score: number | null;
  last_review: string | null;
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
}
