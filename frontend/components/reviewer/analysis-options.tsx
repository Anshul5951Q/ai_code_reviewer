'use client';

import { useState } from 'react';
import { Check } from 'lucide-react';
import { ANALYSIS_OPTIONS } from '@/lib/constants';
import { cn } from '@/lib/utils';

type OptionId = (typeof ANALYSIS_OPTIONS)[number]['id'];

interface AnalysisOptionsProps {
  disabled?: boolean;
}

export function AnalysisOptions({ disabled = false }: AnalysisOptionsProps) {
  const [enabled, setEnabled] = useState<Set<OptionId>>(
    new Set(ANALYSIS_OPTIONS.filter((o) => o.defaultEnabled).map((o) => o.id)),
  );

  const toggle = (id: OptionId) => {
    if (disabled) return;
    setEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <div className="card">
      <h3
        className="text-[13px] font-semibold mb-3"
        style={{ color: 'var(--text-primary)' }}
      >
        Analysis Scope
      </h3>
      <p className="text-[12px] mb-4" style={{ color: 'var(--text-tertiary)' }}>
        Select the analysis modules to run.
      </p>

      <ul className="space-y-3">
        {ANALYSIS_OPTIONS.map((option) => {
          const isEnabled = enabled.has(option.id);
          return (
            <li key={option.id}>
              <button
                onClick={() => toggle(option.id)}
                disabled={disabled}
                className={cn(
                  'w-full flex items-start gap-3 p-3 rounded text-left transition-all',
                  disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:bg-white/[0.02]',
                )}
                style={{
                  background: isEnabled ? 'var(--primary-subtle)' : 'var(--bg-elevated)',
                  border: `1px solid ${isEnabled ? 'var(--primary-border)' : 'var(--border-subtle)'}`,
                }}
                aria-pressed={isEnabled}
                aria-label={option.label}
              >
                {/* Checkbox */}
                <span
                  className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{
                    background: isEnabled ? 'var(--primary)' : 'var(--bg-surface)',
                    border: `1px solid ${isEnabled ? 'var(--primary)' : 'var(--border-default)'}`,
                  }}
                >
                  {isEnabled && <Check size={10} color="white" strokeWidth={3} />}
                </span>

                {/* Content */}
                <div>
                  <p
                    className="text-[13px] font-medium"
                    style={{ color: isEnabled ? 'var(--primary-hover)' : 'var(--text-primary)' }}
                  >
                    {option.label}
                  </p>
                  <p
                    className="text-[12px] mt-0.5 leading-relaxed"
                    style={{ color: 'var(--text-tertiary)' }}
                  >
                    {option.description}
                  </p>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
