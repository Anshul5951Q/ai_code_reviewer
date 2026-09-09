'use client';

import type { DependencyInfo } from '@/types/analysis';

export interface DependencySummaryProps {
  dependencies: DependencyInfo[];
}

export function DependencySummary({ dependencies }: DependencySummaryProps) {
  if (!dependencies || dependencies.length === 0) {
    return <p className="snapshot-empty-text">No dependencies detected.</p>;
  }

  const prod = dependencies.filter(d => d.type === 'dependency').length;
  const dev = dependencies.filter(d => d.type === 'dev_dependency').length;
  const peer = dependencies.filter(d => d.type === 'peer_dependency').length;
  const total = dependencies.length;

  return (
    <div className="dependency-summary">
      <div className="dependency-summary__stats">
        <div className="dependency-stat">
          <span className="dependency-stat__val">{total}</span>
          <span className="dependency-stat__lbl">Total</span>
        </div>
        {prod > 0 && (
          <div className="dependency-stat">
            <span className="dependency-stat__val">{prod}</span>
            <span className="dependency-stat__lbl">Production</span>
          </div>
        )}
        {dev > 0 && (
          <div className="dependency-stat">
            <span className="dependency-stat__val">{dev}</span>
            <span className="dependency-stat__lbl">Dev</span>
          </div>
        )}
        {peer > 0 && (
          <div className="dependency-stat">
            <span className="dependency-stat__val">{peer}</span>
            <span className="dependency-stat__lbl">Peer</span>
          </div>
        )}
      </div>

      <div className="dependency-list-scroll">
        <table className="dependency-table">
          <thead>
            <tr>
              <th>Package</th>
              <th>Version</th>
              <th>Type</th>
              <th>Source Manifest</th>
            </tr>
          </thead>
          <tbody>
            {dependencies.slice(0, 50).map((dep, idx) => (
              <tr key={`${dep.name}-${dep.source_file}-${idx}`}>
                <td className="dep-name">{dep.name}</td>
                <td className="dep-version">{dep.version || 'latest'}</td>
                <td>
                  <span className={`dep-type-badge dep-type-badge--${dep.type}`}>
                    {dep.type}
                  </span>
                </td>
                <td className="dep-source">{dep.source_file}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {dependencies.length > 50 && (
          <p className="dependency-more-note">
            Showing first 50 of {dependencies.length} dependencies.
          </p>
        )}
      </div>
    </div>
  );
}

export default DependencySummary;
