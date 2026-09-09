import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge Tailwind classes without conflicts. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Format a UTC ISO date string into a human-readable relative time. */
export function formatRelativeTime(isoDate: string | null): string {
  if (!isoDate) return '—';
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 30) return date.toLocaleDateString();
  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  if (diffMins > 0) return `${diffMins}m ago`;
  return 'just now';
}

/** Format a score (0–100) to a display string. */
export function formatScore(score: number | null): string {
  if (score === null || score === undefined) return '—';
  return score.toFixed(0);
}

/** Format a duration in milliseconds to a readable string. */
export function formatDuration(ms: number | null): string {
  if (ms === null) return '—';
  const secs = Math.floor(ms / 1000);
  const mins = Math.floor(secs / 60);
  if (mins > 0) return `${mins}m ${secs % 60}s`;
  return `${secs}s`;
}

/** Truncate a commit SHA to its short form (7 chars). */
export function shortSha(sha: string): string {
  return sha.slice(0, 7);
}

/** Truncate a string to a maximum length with ellipsis. */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return `${str.slice(0, maxLength)}…`;
}
