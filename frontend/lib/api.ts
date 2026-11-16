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
import type {
  CorrelatedFinding,
  CorrelatedFindingListResponse,
  CorrelationStatus,
  FindingListResponse,
  SecuritySummary,
} from '@/types/security';
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

function assertValidId(id: string, entityName = 'ID'): void {
  if (!id || typeof id !== 'string' || id.trim() === '' || id === 'undefined') {
    throw new ApiClientError({
      detail: `Invalid or missing ${entityName}.`,
      status: 400,
    });
  }
}

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

const apiCache = new Map<string, CacheEntry<unknown>>();
const inFlightRequests = new Map<string, Promise<unknown>>();

// Default micro-cache TTL: 5000ms (5 seconds) for safe GET requests
const DEFAULT_CACHE_TTL_MS = 5000;

export function clearApiCache(pathPrefix?: string): void {
  if (!pathPrefix) {
    apiCache.clear();
    return;
  }
  for (const key of apiCache.keys()) {
    if (key.includes(pathPrefix)) {
      apiCache.delete(key);
    }
  }
}

export interface RequestOptions extends RequestInit {
  cacheTtlMs?: number;
  skipCache?: boolean;
}

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase();
  const url = `${API_BASE_URL}${path}`;

  // If mutation (POST/PUT/DELETE/PATCH), clear matching cache and bypass
  if (method !== 'GET') {
    if (path.startsWith('/repositories')) clearApiCache('/repositories');
    if (path.startsWith('/reviews')) clearApiCache('/reviews');
    if (path.startsWith('/github')) clearApiCache('/github');
    if (path.startsWith('/remediations')) clearApiCache('/remediations');
    if (path.startsWith('/security')) clearApiCache('/security');
  } else if (!init?.skipCache) {
    const ttl = init?.cacheTtlMs ?? DEFAULT_CACHE_TTL_MS;
    if (ttl > 0) {
      const cached = apiCache.get(url);
      if (cached && Date.now() - cached.timestamp < ttl) {
        return cached.data as T;
      }
    }

    // In-flight request deduplication for identical concurrent GETs
    const inFlight = inFlightRequests.get(url);
    if (inFlight) {
      return inFlight as Promise<T>;
    }
  }

  const executeRequest = async (): Promise<T> => {
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

    const data = (await response.json()) as T;
    if (method === 'GET' && !init?.skipCache) {
      const ttl = init?.cacheTtlMs ?? DEFAULT_CACHE_TTL_MS;
      if (ttl > 0) {
        apiCache.set(url, { data, timestamp: Date.now() });
      }
    }
    return data;
  };

  if (method === 'GET') {
    const promise = executeRequest().finally(() => {
      inFlightRequests.delete(url);
    });
    inFlightRequests.set(url, promise);
    return promise;
  }

  return executeRequest();
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
  assertValidId(id, 'review ID');
  return request<Review>(`/reviews/${encodeURIComponent(id.trim())}`);
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
  assertValidId(reviewId, 'review ID');
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
  AgentRun,
  AgentRunListResponse,
  StartPhase5AnalysisResponse,
} from '@/types/agent';

export async function runReviewAnalysis(
  reviewId: string,
  options?: { wait?: boolean },
): Promise<StartPhase5AnalysisResponse> {
  assertValidId(reviewId, 'review ID');
  const searchParams = new URLSearchParams();
  if (options?.wait) searchParams.set('wait', 'true');
  const q = searchParams.toString();
  return request<StartPhase5AnalysisResponse>(
    `/reviews/${encodeURIComponent(reviewId.trim())}/run${q ? `?${q}` : ''}`,
    { method: 'POST' },
  );
}

export async function getReviewAgents(
  reviewId: string,
): Promise<AgentRunListResponse> {
  assertValidId(reviewId, 'review ID');
  return request<AgentRunListResponse>(`/reviews/${encodeURIComponent(reviewId.trim())}/agents`);
}

export async function getCodeQualityAgent(
  reviewId: string,
): Promise<AgentRun> {
  return request<AgentRun>(`/reviews/${reviewId}/agents/code-quality`);
}

export async function runCodeQualityAgent(
  reviewId: string,
): Promise<AgentRun> {
  return request<AgentRun>(`/reviews/${reviewId}/agents/code-quality`, {
    method: 'POST',
  });
}

export async function getSecurityAgent(
  reviewId: string,
): Promise<AgentRun> {
  return request<AgentRun>(`/reviews/${reviewId}/agents/security`);
}

export async function runSecurityAgent(
  reviewId: string,
): Promise<AgentRun> {
  return request<AgentRun>(`/reviews/${reviewId}/agents/security`, {
    method: 'POST',
  });
}

export interface GateAuditData {
  review_id: string;
  gate_1?: Record<string, unknown> | null;
  gate_2?: Record<string, unknown> | null;
  gate_3?: Record<string, unknown> | null;
}

export async function getGateAudits(
  reviewId: string,
): Promise<GateAuditData> {
  return request<GateAuditData>(`/reviews/${reviewId}/gates`);
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
  assertValidId(reviewId, 'review ID');
  return request<StartAnalysisResponse>(`/reviews/${encodeURIComponent(reviewId.trim())}/analyze`, {
    method: 'POST',
  });
}

export async function getAnalysisStatus(reviewId: string): Promise<AnalysisJob> {
  assertValidId(reviewId, 'review ID');
  return request<AnalysisJob>(`/reviews/${encodeURIComponent(reviewId.trim())}/analysis`);
}

export async function getReviewSnapshot(reviewId: string): Promise<RepositorySnapshot> {
  assertValidId(reviewId, 'review ID');
  return request<RepositorySnapshot>(`/reviews/${encodeURIComponent(reviewId.trim())}/snapshot`);
}

// ---------------------------------------------------------------------------
// AI Remediation & Verification (Phase 6)
// ---------------------------------------------------------------------------

import type {
  BatchRemediationResponse,
  FindingResolutionStatusResponse,
  Gate4AuditReport,
  Gate5DecisionResult,
  PatchRiskAssessment,
  RemediationHistoryResponse,
  RemediationResultResponse,
  RemediationRun,
  VerificationHistoryResponse,
  VerificationResult,
  VerificationRunResponse,
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

export async function remediateCorrelatedFinding(
  reviewId: string,
  correlatedFindingId: string,
  options?: { wait?: boolean }
): Promise<RemediationRun> {
  const query = options?.wait ? '?wait=true' : '';
  return request<RemediationRun>(
    `/reviews/${reviewId}/correlated-findings/${correlatedFindingId}/remediate${query}`,
    {
      method: 'POST',
    }
  );
}

export async function remediateEligibleFindings(
  reviewId: string,
  payload?: { min_confidence?: number; categories?: string[] }
): Promise<BatchRemediationResponse> {
  return request<BatchRemediationResponse>(`/reviews/${reviewId}/remediate-eligible`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
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

export async function getRemediationGate4(
  remediationId: string
): Promise<Gate4AuditReport> {
  return request<Gate4AuditReport>(`/remediations/${remediationId}/gate-4`);
}

export async function getRemediationGate5(
  remediationId: string
): Promise<Gate5DecisionResult> {
  return request<Gate5DecisionResult>(`/remediations/${remediationId}/gate-5`);
}

export async function getRemediationVerificationHistory(
  remediationId: string
): Promise<VerificationHistoryResponse> {
  return request<VerificationHistoryResponse>(`/remediations/${remediationId}/verification-history`);
}

export async function triggerIndependentVerification(
  remediationId: string
): Promise<VerificationRunResponse> {
  return request<VerificationRunResponse>(`/remediations/${remediationId}/verify`, {
    method: 'POST',
  });
}

export async function getFindingResolutionStatus(
  findingId: string
): Promise<FindingResolutionStatusResponse> {
  return request<FindingResolutionStatusResponse>(`/findings/${findingId}/resolution-status`);
}

export async function getRemediationRisk(
  remediationId: string
): Promise<PatchRiskAssessment> {
  return request<PatchRiskAssessment>(`/remediations/${remediationId}/risk`);
}

export async function retryRemediation(
  remediationId: string,
  options?: { wait?: boolean }
): Promise<RemediationRun> {
  const query = options?.wait ? '?wait=true' : '';
  return request<RemediationRun>(`/remediations/${remediationId}/retry${query}`, {
    method: 'POST',
  });
}

export async function getCorrelatedFindingRemediations(
  reviewId: string,
  correlatedFindingId: string
): Promise<RemediationHistoryResponse> {
  return request<RemediationHistoryResponse>(
    `/reviews/${reviewId}/correlated-findings/${correlatedFindingId}/remediations`
  );
}

export async function getFindingRemediations(
  findingId: string
): Promise<RemediationHistoryResponse> {
  return request<RemediationHistoryResponse>(`/findings/${findingId}/remediations`);
}

// ---------------------------------------------------------------------------
// Finding Correlation (Sub-Phase 7.4)
// ---------------------------------------------------------------------------

export async function getCorrelatedFindings(
  reviewId: string,
  params?: {
    severity?: string;
    category?: string;
    relationship_type?: string;
    limit?: number;
    offset?: number;
  }
): Promise<CorrelatedFindingListResponse> {
  assertValidId(reviewId, 'review ID');
  const searchParams = new URLSearchParams();
  if (params?.severity) searchParams.set('severity', params.severity);
  if (params?.category) searchParams.set('category', params.category);
  if (params?.relationship_type) searchParams.set('relationship_type', params.relationship_type);
  if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));
  if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));
  const qs = searchParams.toString();
  const query = qs ? `?${qs}` : '';
  return request<CorrelatedFindingListResponse>(`/reviews/${encodeURIComponent(reviewId.trim())}/correlated-findings${query}`);
}

export async function getSingleCorrelatedFinding(
  reviewId: string,
  findingId: string
): Promise<CorrelatedFinding> {
  assertValidId(reviewId, 'review ID');
  assertValidId(findingId, 'correlated finding ID');
  return request<CorrelatedFinding>(`/reviews/${encodeURIComponent(reviewId.trim())}/correlated-findings/${encodeURIComponent(findingId.trim())}`);
}

export async function getCorrelationStatus(
  reviewId: string
): Promise<CorrelationStatus> {
  assertValidId(reviewId, 'review ID');
  return request<CorrelationStatus>(`/reviews/${encodeURIComponent(reviewId.trim())}/correlation/status`);
}

export async function triggerCorrelation(
  reviewId: string
): Promise<CorrelationStatus> {
  return request<CorrelationStatus>(`/reviews/${reviewId}/correlate`, {
    method: 'POST',
  });
}

