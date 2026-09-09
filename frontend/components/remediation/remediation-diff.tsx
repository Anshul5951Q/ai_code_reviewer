'use client';

import { useState } from 'react';
import { Copy, Check, FileCode, Plus, Minus } from 'lucide-react';

interface RemediationDiffProps {
  diff: string;
  filePath?: string;
}

interface ParsedLine {
  type: 'add' | 'remove' | 'context' | 'header';
  content: string;
  oldLineNumber?: number;
  newLineNumber?: number;
}

export function RemediationDiff({ diff, filePath }: RemediationDiffProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(diff);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Parse unified diff into lines with line numbers and types
  const lines: ParsedLine[] = [];
  let additionsCount = 0;
  let deletionsCount = 0;

  if (diff) {
    const rawLines = diff.split('\n');
    let currentOld = 0;
    let currentNew = 0;

    for (const raw of rawLines) {
      if (raw.startsWith('@@')) {
        // Hunk header: @@ -start,count +start,count @@
        const match = raw.match(/@@\s*-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s*@@/);
        if (match) {
          currentOld = parseInt(match[1], 10);
          currentNew = parseInt(match[2], 10);
        }
        lines.push({ type: 'header', content: raw });
      } else if (raw.startsWith('+') && !raw.startsWith('+++')) {
        additionsCount++;
        lines.push({
          type: 'add',
          content: raw.slice(1),
          newLineNumber: currentNew++,
        });
      } else if (raw.startsWith('-') && !raw.startsWith('---')) {
        deletionsCount++;
        lines.push({
          type: 'remove',
          content: raw.slice(1),
          oldLineNumber: currentOld++,
        });
      } else if (raw.startsWith('---') || raw.startsWith('+++')) {
        lines.push({ type: 'header', content: raw });
      } else {
        lines.push({
          type: 'context',
          content: raw.startsWith(' ') ? raw.slice(1) : raw,
          oldLineNumber: currentOld++,
          newLineNumber: currentNew++,
        });
      }
    }
  }

  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[#0d1117] overflow-hidden font-mono text-xs shadow-inner">
      {/* Diff Toolbar / Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#161b22] border-b border-[var(--border-subtle)] text-[var(--text-secondary)]">
        <div className="flex items-center gap-2 font-medium">
          <FileCode className="w-4 h-4 text-primary-400" />
          <span className="text-[var(--text-primary)]">{filePath || 'Unified Diff'}</span>
          <div className="flex items-center gap-1.5 ml-3">
            <span className="flex items-center text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-1.5 py-0.5 rounded text-[10px]">
              <Plus className="w-3 h-3 mr-0.5" /> {additionsCount}
            </span>
            <span className="flex items-center text-red-400 bg-red-950/40 border border-red-800/40 px-1.5 py-0.5 rounded text-[10px]">
              <Minus className="w-3 h-3 mr-0.5" /> {deletionsCount}
            </span>
          </div>
        </div>

        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-1 rounded bg-white/5 hover:bg-white/10 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
          title="Copy unified diff"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span className="text-[11px]">{copied ? 'Copied' : 'Copy Diff'}</span>
        </button>
      </div>

      {/* Code Viewer */}
      <div className="max-h-96 overflow-x-auto overflow-y-auto divide-y divide-white/5">
        {lines.length === 0 ? (
          <div className="p-4 text-center text-[var(--text-muted)] italic">
            No diff lines available.
          </div>
        ) : (
          lines.map((line, idx) => {
            if (line.type === 'header') {
              return (
                <div
                  key={idx}
                  className="bg-[#1b222d] text-blue-300/80 px-4 py-1 select-none text-[11px] font-semibold"
                >
                  {line.content}
                </div>
              );
            }

            const isAdd = line.type === 'add';
            const isRemove = line.type === 'remove';

            return (
              <div
                key={idx}
                className={`flex items-start hover:brightness-110 transition-colors ${
                  isAdd
                    ? 'bg-emerald-950/25 text-emerald-200'
                    : isRemove
                    ? 'bg-red-950/25 text-red-200'
                    : 'text-slate-300'
                }`}
              >
                {/* Old line number */}
                <div className="w-10 py-1 text-right pr-2 select-none text-[var(--text-muted)] opacity-50 bg-black/20 flex-shrink-0">
                  {line.oldLineNumber ?? ''}
                </div>

                {/* New line number */}
                <div className="w-10 py-1 text-right pr-2 select-none text-[var(--text-muted)] opacity-50 bg-black/20 border-r border-white/5 flex-shrink-0">
                  {line.newLineNumber ?? ''}
                </div>

                {/* Sign column */}
                <div className="w-6 py-1 text-center select-none font-bold flex-shrink-0">
                  {isAdd && <span className="text-emerald-400">+</span>}
                  {isRemove && <span className="text-red-400">-</span>}
                </div>

                {/* Code content */}
                <div className="flex-1 py-1 px-2 whitespace-pre overflow-x-auto">
                  {line.content || ' '}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
