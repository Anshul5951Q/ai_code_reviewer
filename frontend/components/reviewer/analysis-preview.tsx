import { Info, GitBranch, Code2, Shield, Wrench, CheckCircle } from 'lucide-react';

interface AnalysisPreviewProps {
  repositoryConnected?: boolean;
}

const PIPELINE_STEPS = [
  { icon: Code2, label: 'Code Understanding', description: 'Parse structure & dependencies' },
  { icon: Shield, label: 'Security Detection', description: 'Scan for vulnerabilities' },
  { icon: Info, label: 'Quality Analysis', description: 'Evaluate code patterns' },
  { icon: Wrench, label: 'Remediation', description: 'Generate fix suggestions' },
  { icon: CheckCircle, label: 'Verification', description: 'Validate fixes are safe' },
] as const;

export function AnalysisPreview({ repositoryConnected = false }: AnalysisPreviewProps) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <GitBranch size={14} style={{ color: 'var(--text-tertiary)' }} />
        <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
          Analysis Pipeline
        </h3>
      </div>

      {!repositoryConnected && (
        <div
          className="flex items-start gap-2 p-3 rounded mb-4 text-[12px]"
          style={{
            background: 'var(--primary-subtle)',
            border: '1px solid var(--primary-border)',
            color: 'var(--primary-hover)',
          }}
        >
          <Info size={13} className="mt-0.5 flex-shrink-0" />
          <span>
            Configure a repository above to enable analysis. The full pipeline below
            will run once a repository is connected.
          </span>
        </div>
      )}

      <ol className="space-y-3">
        {PIPELINE_STEPS.map((step, index) => {
          const Icon = step.icon;
          return (
            <li
              key={step.label}
              className="flex items-center gap-3"
              style={{ opacity: repositoryConnected ? 1 : 0.45 }}
            >
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0"
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-default)',
                  color: 'var(--text-tertiary)',
                }}
              >
                {index + 1}
              </div>
              <div
                className="w-7 h-7 rounded flex items-center justify-center flex-shrink-0"
                style={{ background: 'var(--bg-elevated)' }}
              >
                <Icon size={13} style={{ color: 'var(--text-secondary)' }} />
              </div>
              <div>
                <p className="text-[12px] font-medium" style={{ color: 'var(--text-primary)' }}>
                  {step.label}
                </p>
                <p className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                  {step.description}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
