'use client';

import type { RepositorySnapshot } from '@/types/analysis';
import {
  CheckCircle,
  FileCode2,
  TestTube,
  Settings,
  BookOpen,
  Package,
} from 'lucide-react';
import { LanguageBreakdown } from './language-breakdown';
import { DependencySummary } from './dependency-summary';

interface RepositorySnapshotCardProps {
  snapshot: RepositorySnapshot;
}

export function RepositorySnapshotCard({ snapshot }: RepositorySnapshotCardProps) {
  const frameworks = snapshot.frameworks ?? [];

  return (
    <div className="repository-snapshot">
      <div className="repository-snapshot__header">
        <CheckCircle size={24} className="repository-snapshot__icon" />
        <div>
          <h3 className="repository-snapshot__title">Repository Ready</h3>
          <p className="repository-snapshot__subtitle">
            Analysis complete at commit{' '}
            <code className="mono">{snapshot.commit_sha.slice(0, 7)}</code>
          </p>
        </div>
      </div>

      {/* File count stats */}
      <div className="snapshot-stat-grid">
        <div className="snapshot-stat">
          <FileCode2 size={18} className="snapshot-stat__icon" />
          <span className="snapshot-stat__number">{snapshot.total_files}</span>
          <span className="snapshot-stat__label">Total Files</span>
        </div>
        <div className="snapshot-stat">
          <BookOpen size={18} className="snapshot-stat__icon" />
          <span className="snapshot-stat__number">{snapshot.source_files}</span>
          <span className="snapshot-stat__label">Source Files</span>
        </div>
        <div className="snapshot-stat">
          <TestTube size={18} className="snapshot-stat__icon" />
          <span className="snapshot-stat__number">{snapshot.test_files}</span>
          <span className="snapshot-stat__label">Test Files</span>
        </div>
        <div className="snapshot-stat">
          <Settings size={18} className="snapshot-stat__icon" />
          <span className="snapshot-stat__number">{snapshot.config_files}</span>
          <span className="snapshot-stat__label">Config Files</span>
        </div>
        <div className="snapshot-stat">
          <Package size={18} className="snapshot-stat__icon" />
          <span className="snapshot-stat__number">
            {snapshot.total_lines.toLocaleString()}
          </span>
          <span className="snapshot-stat__label">Lines of Code</span>
        </div>
      </div>

      {/* Frameworks */}
      {frameworks.length > 0 && (
        <div className="snapshot-section">
          <h4 className="snapshot-section__title">Detected Frameworks</h4>
          <div className="framework-tags">
            {frameworks.map(fw => (
              <span key={fw} className="framework-tag">{fw}</span>
            ))}
          </div>
        </div>
      )}

      {/* Languages */}
      <div className="snapshot-section">
        <h4 className="snapshot-section__title">Language Breakdown</h4>
        <LanguageBreakdown languages={snapshot.languages} />
      </div>

      {/* Dependencies */}
      <div className="snapshot-section">
        <h4 className="snapshot-section__title">Dependencies</h4>
        <DependencySummary dependencies={snapshot.dependencies ?? []} />
      </div>

      {/* Entry points */}
      {snapshot.structure?.entry_points && snapshot.structure.entry_points.length > 0 && (
        <div className="snapshot-section">
          <h4 className="snapshot-section__title">Entry Points</h4>
          <div className="entry-points-list">
            {snapshot.structure.entry_points.map(ep => (
              <code key={ep} className="entry-point">{ep}</code>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default RepositorySnapshotCard;
