'use client';

import type { LanguageStat } from '@/types/analysis';

const LANG_COLORS: Record<string, string> = {
  TypeScript: '#3178c6',
  JavaScript: '#f7df1e',
  Python: '#3572A5',
  Java: '#b07219',
  Go: '#00ADD8',
  Rust: '#dea584',
  'C++': '#f34b7d',
  C: '#555555',
  'C#': '#178600',
  Ruby: '#701516',
  Swift: '#F05138',
  Kotlin: '#A97BFF',
  PHP: '#4F5D95',
  HTML: '#e34c26',
  CSS: '#563d7c',
  YAML: '#cb171e',
  JSON: '#292929',
  SQL: '#e38c00',
  Shell: '#89e051',
  Markdown: '#083fa1',
  Vue: '#4FC08D',
  Svelte: '#ff3e00',
};

function getColor(lang: string): string {
  return LANG_COLORS[lang] ?? '#6b7280';
}

export interface LanguageBreakdownProps {
  languages: Record<string, LanguageStat>;
}

export function LanguageBreakdown({ languages }: LanguageBreakdownProps) {
  const entries = Object.entries(languages).sort((a, b) => b[1].percentage - a[1].percentage);

  if (entries.length === 0) {
    return <p className="snapshot-empty-text">No languages detected.</p>;
  }

  return (
    <div className="language-breakdown">
      {/* Stacked bar */}
      <div className="language-bar">
        {entries.map(([lang, stat]) => (
          <div
            key={lang}
            className="language-bar__segment"
            style={{ width: `${stat.percentage}%`, background: getColor(lang) }}
            title={`${lang}: ${stat.percentage}%`}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="language-legend">
        {entries.map(([lang, stat]) => (
          <div key={lang} className="language-legend__item">
            <span
              className="language-legend__dot"
              style={{ background: getColor(lang) }}
            />
            <span className="language-legend__name">{lang}</span>
            <span className="language-legend__pct">{stat.percentage}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default LanguageBreakdown;
