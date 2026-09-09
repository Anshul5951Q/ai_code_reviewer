import { Shield } from 'lucide-react';

interface SecurityScoreProps {
  score: number | null;
  label?: string;
}

export function SecurityScore({ score, label = 'Security Score' }: SecurityScoreProps) {
  const displayScore = score !== null ? Math.round(score) : null;
  const scoreColor =
    displayScore === null
      ? 'var(--text-tertiary)'
      : displayScore >= 80
        ? 'var(--success)'
        : displayScore >= 60
          ? 'var(--warning)'
          : 'var(--critical)';

  return (
    <div className="card flex flex-col items-center justify-center py-6 gap-3">
      {/* Icon ring */}
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center"
        style={{
          background: displayScore === null ? 'var(--bg-elevated)' : `${scoreColor}18`,
          border: `2px solid ${displayScore === null ? 'var(--border-default)' : scoreColor}`,
        }}
      >
        <Shield size={22} style={{ color: scoreColor }} />
      </div>

      {/* Score value */}
      <div className="text-center">
        <p
          className="text-3xl font-semibold tabular-nums"
          style={{ color: scoreColor }}
        >
          {displayScore !== null ? displayScore : '—'}
          {displayScore !== null && (
            <span className="text-lg text-current opacity-60">/100</span>
          )}
        </p>
        <p
          className="text-[12px] mt-1"
          style={{ color: 'var(--text-tertiary)' }}
        >
          {displayScore === null ? 'No repositories analyzed' : label}
        </p>
      </div>
    </div>
  );
}
