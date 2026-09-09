/**
 * Centralized API client for the AI Code Reviewer backend.
 *
 * All backend communication must go through this module.
 * Do NOT use fetch() or axios directly in components.
 *
 * Base URL is configured via NEXT_PUBLIC_API_URL environment variable.
 */

import type {
  Repository,
  RepositoryCreate,
  RepositoryListResponse,
} from '@/types/repository';
import type { Review, ReviewListResponse } from '@/types/review';
import type { FindingListResponse, SecuritySummary } from '@/types/security';
import type {
  GitHubBranch,
  GitHubCommit,
  GitHubDisconnectResponse,
  GitHubFileContent,
  GitHubRepoFilters,
  GitHubRepoItem,
  GitHubStatusResponse,
  GitHubTreeItem,
} from '@/types/github';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api';

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

export interface ApiError {
  detail: string;
  status: number;
}

export class ApiClientError extends Error {
  public readonly status: number;
  public readonly detail: string;

  constructor(error: ApiError) {
    super(error.detail);
    this.status = error.status;
    this.detail = error.detail;
    this.name = 'ApiClientError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  const response = await fetch(url, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiClientError({ status: response.status, detail });
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthStatus {
  status: string;
  version: string;
  environment: string;
}

export async function getHealthStatus(): Promise<HealthStatus> {
  return request<HealthStatus>('/health');
}

// ---------------------------------------------------------------------------
// Repositories
// ---------------------------------------------------------------------------

export async function getRepositories(params?: {
  q?: string;
  limit?: number;
  offset?: number;
}): Promise<RepositoryListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.q) searchParams.set('q', params.q);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());
  const query = searchParams.toString();
  return request<RepositoryListResponse>(`/repositories${query ? `?${query}` : ''}`);
}

export async function getRepository(id: string): Promise<Repository> {
  return request<Repository>(`/repositories/${id}`);
}

export async function createRepository(data: RepositoryCreate): Promise<Repository> {
  return request<Repository>('/repositories', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteRepository(id: string): Promise<void> {
  await request<void>(`/repositories/${id}`, {
    method: 'DELETE',
  });
}

// ---------------------------------------------------------------------------
// Repository GitHub Proxy Endpoints
// ---------------------------------------------------------------------------

export async function getRepoBranches(repositoryId: string): Promise<GitHubBranch[]> {
  return request<GitHubBranch[]>(`/repositories/${repositoryId}/branches`);
}

export async function getRepoCommits(
  repositoryId: string,
  branch?: string,
  limit?: number,
): Promise<GitHubCommit[]> {
  const searchParams = new URLSearchParams();
  if (branch) searchParams.set('branch', branch);
  if (limit) searchParams.set('limit', limit.toString());
  const query = searchParams.toString();
  return request<GitHubCommit[]>(
    `/repositories/${repositoryId}/commits${query ? `?${query}` : ''}`,
  );
}

export async function getRepoTree(
  repositoryId: string,
  treeSha?: string,
  recursive = true,
): Promise<GitHubTreeItem[]> {
  const searchParams = new URLSearchParams();
  if (treeSha) searchParams.set('tree_sha', treeSha);
  if (recursive) searchParams.set('recursive', 'true');
  const query = searchParams.toString();
  return request<GitHubTreeItem[]>(
    `/repositories/${repositoryId}/tree${query ? `?${query}` : ''}`,
  );
}

export async function getRepoContent(
  repositoryId: string,
  path: string,
  ref?: string,
): Promise<GitHubFileContent> {
  const searchParams = new URLSearchParams();
  searchParams.set('path', path);
  if (ref) searchParams.set('ref', ref);
  return request<GitHubFileContent>(
    `/repositories/${repositoryId}/content?${searchParams.toString()}`,
  );
}

// ---------------------------------------------------------------------------
// Direct GitHub API
// ---------------------------------------------------------------------------

export async function getGitHubStatus(): Promise<GitHubStatusResponse> {
  return request<GitHubStatusResponse>('/github/status');
}

export function connectGitHub(): void {
  // Navigate to FastAPI OAuth endpoint which redirects to GitHub
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = `${API_BASE_URL}/github/connect`;
}

export async function connectGitHubToken(token: string): Promise<GitHubStatusResponse> {
  return request<GitHubStatusResponse>('/github/connect-token', {
    method: 'POST',
    body: JSON.stringify({ token }),
  });
}

export async function disconnectGitHub(): Promise<GitHubDisconnectResponse> {
  return request<GitHubDisconnectResponse>('/github/connection', {
    method: 'DELETE',
  });
}

export async function getGitHubRepositories(
  params?: GitHubRepoFilters,
): Promise<GitHubRepoItem[]> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.page) searchParams.set('page', params.page.toString());
  if (params?.type && params.type !== 'all') searchParams.set('type', params.type);
  if (params?.visibility && params.visibility !== 'all') searchParams.set('visibility', params.visibility);
  if (params?.affiliation) searchParams.set('affiliation', params.affiliation);
  if (params?.search) searchParams.set('q', params.search);
  const q = searchParams.toString();
  return request<GitHubRepoItem[]>(`/github/repositories${q ? `?${q}` : ''}`);
}

export async function getGitHubBranches(owner: string, repo: string): Promise<GitHubBranch[]> {
  return request<GitHubBranch[]>(`/github/branches?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}`);
}

export async function getGitHubCommits(
  owner: string,
  repo: string,
  branch?: string,
  limit = 30,
): Promise<GitHubCommit[]> {
  const searchParams = new URLSearchParams();
  searchParams.set('owner', owner);
  searchParams.set('repo', repo);
  if (branch) searchParams.set('branch', branch);
  searchParams.set('limit', limit.toString());
  return request<GitHubCommit[]>(`/github/commits?${searchParams.toString()}`);
}

// ---------------------------------------------------------------------------
// Reviews
// ---------------------------------------------------------------------------

export async function getReviews(params?: {
  repository_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<ReviewListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.repository_id) searchParams.set('repository_id', params.repository_id);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());
  const query = searchParams.toString();
  return request<ReviewListResponse>(`/reviews${query ? `?${query}` : ''}`);
}

export async function getReview(id: string): Promise<Review> {
  return request<Review>(`/reviews/${id}`);
}

export async function createReview(data: {
  repository_id: string;
  commit_sha: string;
  branch: string;
}): Promise<Review> {
  return request<Review>('/reviews', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getReviewFindings(
  reviewId: string,
  params?: {
    severity?: string;
    category?: string;
    status?: string;
    agent_type?: string;
    file_path?: string;
    limit?: number;
    offset?: number;
  },
): Promise<FindingListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.severity) searchParams.set('severity', params.severity);
  if (params?.category) searchParams.set('category', params.category);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.agent_type) searchParams.set('agent_type', params.agent_type);
  if (params?.file_path) searchParams.set('file_path', params.file_path);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());
  const query = searchParams.toString();
  return request<FindingListResponse>(`/reviews/${reviewId}/findings${query ? `?${query}` : ''}`);
}

// ---------------------------------------------------------------------------
// Multi-Agent Analysis (Phase 5)
// ---------------------------------------------------------------------------

import type {
  AgentRunListResponse,
  StartPhase5AnalysisResponse,
} from '@/types/agent';

export async function runReviewAnalysis(
  reviewId: string,
  options?: { wait?: boolean },
): Promise<StartPhase5AnalysisResponse> {
  const searchParams = new URLSearchParams();
  if (options?.wait) searchParams.set('wait', 'true');
  const q = searchParams.toString();
  return request<StartPhase5AnalysisResponse>(
    `/reviews/${reviewId}/run${q ? `?${q}` : ''}`,
    { method: 'POST' },
  );
}

export async function getReviewAgents(
  reviewId: string,
): Promise<AgentRunListResponse> {
  return request<AgentRunListResponse>(`/reviews/${reviewId}/agents`);
}

// ---------------------------------------------------------------------------
// Security
// ---------------------------------------------------------------------------

export async function getSecuritySummary(): Promise<SecuritySummary> {
  return request<SecuritySummary>('/security/summary');
}

export async function getSecurityFindings(params?: {
  severity?: string;
  category?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<FindingListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.severity) searchParams.set('severity', params.severity);
  if (params?.category) searchParams.set('category', params.category);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());
  const query = searchParams.toString();
  return request<FindingListResponse>(`/security/findings${query ? `?${query}` : ''}`);
}

// ---------------------------------------------------------------------------
// Analysis (Phase 3)
// ---------------------------------------------------------------------------

import type {
  AnalysisJob,
  RepositorySnapshot,
  StartAnalysisResponse,
} from '@/types/analysis';

export async function startAnalysis(reviewId: string): Promise<StartAnalysisResponse> {
  return request<StartAnalysisResponse>(`/reviews/${reviewId}/analyze`, {
    method: 'POST',
  });
}

export async function getAnalysisStatus(reviewId: string): Promise<AnalysisJob> {
  return request<AnalysisJob>(`/reviews/${reviewId}/analysis`);
}

export async function getReviewSnapshot(reviewId: string): Promise<RepositorySnapshot> {
  return request<RepositorySnapshot>(`/reviews/${reviewId}/snapshot`);
}

// ---------------------------------------------------------------------------
// AI Remediation & Verification (Phase 6)
// ---------------------------------------------------------------------------

import type {
  RemediationHistoryResponse,
  RemediationResultResponse,
  RemediationRun,
  VerificationResult,
} from '@/types/remediation';

export async function remediateFinding(
  findingId: string,
  options?: { wait?: boolean }
): Promise<RemediationRun> {
  const query = options?.wait ? '?wait=true' : '';
  return request<RemediationRun>(`/findings/${findingId}/remediate${query}`, {
    method: 'POST',
  });
}

export async function getRemediation(remediationId: string): Promise<RemediationRun> {
  return request<RemediationRun>(`/remediations/${remediationId}`);
}

export async function getRemediationResult(
  remediationId: string
): Promise<RemediationResultResponse> {
  return request<RemediationResultResponse>(`/remediations/${remediationId}/result`);
}

export async function getRemediationVerification(
  remediationId: string
): Promise<VerificationResult> {
  return request<VerificationResult>(`/remediations/${remediationId}/verification`);
}

export async function getFindingRemediations(
  findingId: string
): Promise<RemediationHistoryResponse> {
  return request<RemediationHistoryResponse>(`/findings/${findingId}/remediations`);
}

