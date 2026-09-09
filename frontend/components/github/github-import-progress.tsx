'use client';

import { CheckCircle2, Loader2, AlertCircle, X } from 'lucide-react';

export interface ImportItemStatus {
  name: string;
  status: 'pending' | 'importing' | 'completed' | 'failed' | 'already_imported';
  error?: string;
}

interface GitHubImportProgressProps {
  items: ImportItemStatus[];
  isOpen: boolean;
  onClose: () => void;
  isFinished: boolean;
}

export function GitHubImportProgress({
  items,
  isOpen,
  onClose,
  isFinished,
}: GitHubImportProgressProps) {
  if (!isOpen) return null;

  const completedCount = items.filter(
    (i) => i.status === 'completed' || i.status === 'already_imported',
  ).length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div
        className="w-full max-w-md rounded-xl p-6 shadow-2xl relative flex flex-col max-h-[85vh]"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-strong)',
        }}
      >
        {isFinished && (
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        )}

        <div className="mb-4">
          <h3 className="text-base font-semibold text-white">
            {isFinished ? 'Import Complete' : 'Importing Repositories…'}
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            {completedCount} of {items.length} repositories processed
          </p>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden mb-4">
          <div
            className="h-full bg-indigo-500 transition-all duration-300 rounded-full"
            style={{ width: `${(completedCount / Math.max(items.length, 1)) * 100}%` }}
          />
        </div>

        {/* Items List */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1 -mr-1">
          {items.map((item) => (
            <div
              key={item.name}
              className="flex items-center justify-between p-2.5 rounded-lg text-xs"
              style={{ background: 'var(--bg-elevated)' }}
            >
              <span className="font-mono text-zinc-200 truncate mr-2">{item.name}</span>

              <div className="flex items-center gap-1.5 flex-shrink-0">
                {item.status === 'pending' && (
                  <span className="text-zinc-500">Waiting</span>
                )}
                {item.status === 'importing' && (
                  <span className="text-indigo-400 flex items-center gap-1">
                    <Loader2 size={12} className="animate-spin" />
                    <span>Importing</span>
                  </span>
                )}
                {item.status === 'completed' && (
                  <span className="text-emerald-400 flex items-center gap-1 font-medium">
                    <CheckCircle2 size={13} />
                    <span>Imported</span>
                  </span>
                )}
                {item.status === 'already_imported' && (
                  <span className="text-zinc-400 flex items-center gap-1">
                    <CheckCircle2 size={13} className="text-zinc-500" />
                    <span>Already imported</span>
                  </span>
                )}
                {item.status === 'failed' && (
                  <span className="text-red-400 flex items-center gap-1" title={item.error}>
                    <AlertCircle size={13} />
                    <span>Failed</span>
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        {isFinished && (
          <div className="mt-5 pt-3 border-t border-white/5 flex justify-end">
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-xs font-medium rounded-lg text-white"
              style={{ background: 'var(--primary)' }}
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default GitHubImportProgress;
