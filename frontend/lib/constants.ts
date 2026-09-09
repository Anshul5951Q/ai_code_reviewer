import type { Severity } from '@/types/security';
import type { ReviewStatus } from '@/types/review';

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

export const NAV_ITEMS = [
  {
    group: 'WORKSPACE',
    items: [
      { label: 'Dashboard', href: '/dashboard', icon: 'LayoutDashboard' },
      { label: 'Repositories', href: '/dashboard/repositories', icon: 'GitBranch' },
      { label: 'Reviewer', href: '/dashboard/reviewer', icon: 'ScanSearch' },
      { label: 'Reviews', href: '/dashboard/reviews', icon: 'ClipboardList' },
    ],
  },
  {
    group: 'SECURITY',
    items: [
      { label: 'Security', href: '/dashboard/security', icon: 'ShieldAlert' },
    ],
  },
  {
    group: 'SYSTEM',
    items: [
      { label: 'Settings', href: '/dashboard/settings', icon: 'Settings' },
    ],
  },
] as const;

// ---------------------------------------------------------------------------
// Severity configuration
// ---------------------------------------------------------------------------

export const SEVERITY_CONFIG: Record<
  Severity,
  { label: string; color: string; bgColor: string; borderColor: string }
> = {
  critical: {
    label: 'Critical',
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
  },
  high: {
    label: 'High',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/30',
  },
  medium: {
    label: 'Medium',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/30',
  },
  low: {
    label: 'Low',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
  },
  info: {
    label: 'Info',
    color: 'text-zinc-400',
    bgColor: 'bg-zinc-500/10',
    borderColor: 'border-zinc-500/30',
  },
};

// ---------------------------------------------------------------------------
// Review status configuration
// ---------------------------------------------------------------------------

export const STATUS_CONFIG: Record<
  ReviewStatus,
  { label: string; color: string; bgColor: string; dotColor: string }
> = {
  queued: {
    label: 'Queued',
    color: 'text-zinc-400',
    bgColor: 'bg-zinc-500/10',
    dotColor: 'bg-zinc-400',
  },
  ingesting: {
    label: 'Ingesting',
    color: 'text-indigo-400',
    bgColor: 'bg-indigo-500/10',
    dotColor: 'bg-indigo-400',
  },
  ready_for_analysis: {
    label: 'Ready for Analysis',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    dotColor: 'bg-emerald-400',
  },
  running: {
    label: 'Running',
    color: 'text-indigo-400',
    bgColor: 'bg-indigo-500/10',
    dotColor: 'bg-indigo-400',
  },
  completed: {
    label: 'Completed',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    dotColor: 'bg-emerald-400',
  },
  completed_with_warnings: {
    label: 'Completed with Warnings',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    dotColor: 'bg-amber-400',
  },
  failed: {
    label: 'Failed',
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    dotColor: 'bg-red-400',
  },
  cancelled: {
    label: 'Cancelled',
    color: 'text-zinc-500',
    bgColor: 'bg-zinc-500/10',
    dotColor: 'bg-zinc-500',
  },
};

// ---------------------------------------------------------------------------
// Demo visualization data (CLEARLY ISOLATED — replace with API calls)
// These are ONLY used for chart visualization. They do NOT represent real data.
// ---------------------------------------------------------------------------

export const DEMO_REVIEW_ACTIVITY = [
  { date: 'Mon', reviews: 0 },
  { date: 'Tue', reviews: 0 },
  { date: 'Wed', reviews: 0 },
  { date: 'Thu', reviews: 0 },
  { date: 'Fri', reviews: 0 },
  { date: 'Sat', reviews: 0 },
  { date: 'Sun', reviews: 0 },
];

export const DEMO_SECURITY_TREND = [
  { date: 'Week 1', score: null },
  { date: 'Week 2', score: null },
  { date: 'Week 3', score: null },
  { date: 'Week 4', score: null },
];

export const DEMO_FINDING_DISTRIBUTION = [
  { name: 'Critical', value: 0, color: '#ef4444' },
  { name: 'High', value: 0, color: '#f97316' },
  { name: 'Medium', value: 0, color: '#f59e0b' },
  { name: 'Low', value: 0, color: '#60a5fa' },
];

// ---------------------------------------------------------------------------
// Analysis options
// ---------------------------------------------------------------------------

export const ANALYSIS_OPTIONS = [
  {
    id: 'code_understanding',
    label: 'Code Understanding',
    description: 'Parse and model the repository structure, dependencies, and call graphs.',
    defaultEnabled: true,
  },
  {
    id: 'code_quality',
    label: 'Code Quality',
    description: 'Detect anti-patterns, complexity issues, dead code, and maintainability risks.',
    defaultEnabled: true,
  },
  {
    id: 'security_detection',
    label: 'Security Detection',
    description: 'Identify vulnerabilities, insecure patterns, secrets, and dependency risks.',
    defaultEnabled: true,
  },
  {
    id: 'remediation',
    label: 'Remediation',
    description: 'Generate actionable fix suggestions and code patches for identified issues.',
    defaultEnabled: true,
  },
  {
    id: 'verification',
    label: 'Verification',
    description: 'Validate that proposed remediations resolve findings without introducing regressions.',
    defaultEnabled: true,
  },
] as const;
