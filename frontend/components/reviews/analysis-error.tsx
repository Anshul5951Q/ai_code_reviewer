'use client';

import { AlertTriangle, RefreshCw } from 'lucide-react';

interface AnalysisErrorCardProps {
  error: string;
  onRetry?: () => void;
}

export function AnalysisErrorCard({ error, onRetry }: AnalysisErrorCardProps) {
  return (
    <div className="analysis-error-card">
      <div className="analysis-error-card__icon">
        <AlertTriangle size={32} />
      </div>
      <h3 className="analysis-error-card__title">Analysis Failed</h3>
      <p className="analysis-error-card__message">{error}</p>
      {onRetry && (
        <button
          className="btn btn-secondary analysis-error-card__retry"
          onClick={onRetry}
        >
          <RefreshCw size={16} />
          Retry Analysis
        </button>
      )}
    </div>
  );
}
