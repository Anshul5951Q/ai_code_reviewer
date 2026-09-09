'use client';

import { CheckCircle, Circle, Loader2 } from 'lucide-react';
import type { AnalysisStage } from '@/types/analysis';
import { STAGE_LABELS, STAGES_ORDER } from '@/types/analysis';

export interface AnalysisStageRowProps {
  stage: AnalysisStage;
  currentStage: AnalysisStage | null;
  jobStatus: string;
}

export type StageState = 'pending' | 'active' | 'done';

export function getStageState(
  stage: AnalysisStage,
  currentStage: AnalysisStage | null,
  jobStatus: string,
): StageState {
  if (jobStatus === 'completed') return 'done';
  if (!currentStage) return 'pending';

  const currentIdx = STAGES_ORDER.indexOf(currentStage);
  const stageIdx = STAGES_ORDER.indexOf(stage);

  if (stageIdx < currentIdx) return 'done';
  if (stageIdx === currentIdx) return 'active';
  return 'pending';
}

export function AnalysisStageRow({ stage, currentStage, jobStatus }: AnalysisStageRowProps) {
  const state = getStageState(stage, currentStage, jobStatus);

  return (
    <div className={`analysis-stage analysis-stage--${state}`}>
      <div className="analysis-stage__icon">
        {state === 'done' && <CheckCircle size={18} className="analysis-stage__check" />}
        {state === 'active' && <Loader2 size={18} className="analysis-stage__spinner spin" />}
        {state === 'pending' && <Circle size={18} className="analysis-stage__circle" />}
      </div>
      <span className="analysis-stage__label">{STAGE_LABELS[stage] ?? stage}</span>
      {state === 'active' && (
        <span className="analysis-stage__badge">In Progress</span>
      )}
    </div>
  );
}

export default AnalysisStageRow;
