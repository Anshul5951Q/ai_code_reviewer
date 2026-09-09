'use client';

export interface AnalysisProgressBarProps {
  progress: number;
  filesProcessed: number;
  filesTotal: number;
}

export function AnalysisProgressBar({
  progress,
  filesProcessed,
  filesTotal,
}: AnalysisProgressBarProps) {
  const boundedProgress = Math.max(0, Math.min(100, Math.round(progress)));

  return (
    <div className="analysis-progress-bar-container">
      <div className="analysis-progress-bar-header">
        <span className="analysis-progress-bar-label">Overall Progress</span>
        <div className="analysis-progress-bar-stats">
          {filesTotal > 0 && (
            <span className="analysis-progress-bar-files">
              {filesProcessed} / {filesTotal} files
            </span>
          )}
          <span className="analysis-progress-bar-pct">{boundedProgress}%</span>
        </div>
      </div>
      <div className="analysis-progress-bar-track">
        <div
          className="analysis-progress-bar-fill"
          style={{ width: `${boundedProgress}%` }}
        />
      </div>
    </div>
  );
}

export default AnalysisProgressBar;
