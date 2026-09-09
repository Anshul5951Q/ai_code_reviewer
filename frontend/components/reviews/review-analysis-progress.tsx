'use client';

import { Loader2 } from 'lucide-react';
import type { AnalysisJob } from '@/types/analysis';
import { STAGES_ORDER } from '@/types/analysis';
import { AnalysisStageRow } from './analysis-stage';
import { AnalysisProgressBar } from './analysis-progress-bar';

interface ReviewAnalysisProgressProps {
  job: AnalysisJob;
}

export function ReviewAnalysisProgress({ job }: ReviewAnalysisProgressProps) {
  return (
    <div className="review-analysis-progress">
      <div className="review-analysis-progress__header">
        <h3 className="review-analysis-progress__title">
          <Loader2 size={20} className="spin" />
          Analyzing Repository
        </h3>
        <span className="review-analysis-progress__status-badge">
          {job.status.replace(/_/g, ' ')}
        </span>
      </div>

      <AnalysisProgressBar
        progress={job.progress}
        filesProcessed={job.files_processed}
        filesTotal={job.files_total}
      />

      <div className="review-analysis-stages">
        {STAGES_ORDER.filter(s => s !== 'completed').map(stage => (
          <AnalysisStageRow
            key={stage}
            stage={stage}
            currentStage={job.current_stage}
            jobStatus={job.status}
          />
        ))}
      </div>
    </div>
  );
}

export default ReviewAnalysisProgress;
