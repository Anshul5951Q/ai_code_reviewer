import { type ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1
          className="text-xl font-semibold leading-tight"
          style={{ color: 'var(--text-primary)' }}
        >
          {title}
        </h1>
        {description && (
          <p
            className="mt-1 text-[13px] leading-relaxed"
            style={{ color: 'var(--text-secondary)' }}
          >
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>
      )}
    </div>
  );
}
