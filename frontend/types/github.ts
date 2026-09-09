export interface GitHubStatusResponse {
  connected: boolean;
  github_login?: string | null;
  avatar_url?: string | null;
  last_verified_at?: string | null;
  authenticated_user?: string | null;
  user_name?: string | null;
  scopes?: string[];
  rate_limit_limit?: number | null;
  rate_limit_remaining?: number | null;
  rate_limit_reset?: number | null;
  error?: string | null;
  oauth_configured?: boolean;
}

export interface GitHubDisconnectResponse {
  disconnected: boolean;
  message: string;
}

export interface GitHubRepoItem {
  id: number;
  name: string;
  full_name: string;
  owner: string;
  html_url: string;
  default_branch: string;
  visibility: string;
  language?: string | null;
  description?: string | null;
  updated_at?: string | null;
}

export interface GitHubRepoFilters {
  search?: string;
  type?: 'all' | 'owner' | 'member' | 'public' | 'private';
  visibility?: 'all' | 'public' | 'private';
  affiliation?: string;
  page?: number;
  limit?: number;
  per_page?: number;
}

export interface GitHubBranch {
  name: string;
  commit_sha: string;
  protected?: boolean;
}

export interface GitHubCommit {
  sha: string;
  short_sha: string;
  message: string;
  author_name: string;
  author_email?: string | null;
  date: string;
  html_url?: string | null;
}

export interface GitHubTreeItem {
  path: string;
  mode: string;
  type: string;
  sha: string;
  size?: number | null;
}

export interface GitHubFileContent {
  path: string;
  sha: string;
  size: number;
  encoding: string;
  content?: string | null;
}
