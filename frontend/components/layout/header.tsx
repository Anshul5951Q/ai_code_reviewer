'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';

const ROUTE_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  repositories: 'Repositories',
  reviewer: 'Reviewer',
  reviews: 'Reviews',
  security: 'Security',
  settings: 'Settings',
};

export function Header() {
  const pathname = usePathname();
  const segments = pathname.split('/').filter(Boolean);

  return (
    <nav
      className="flex items-center gap-1 text-[12px]"
      aria-label="Breadcrumb"
    >
      {segments.map((segment, index) => {
        const href = '/' + segments.slice(0, index + 1).join('/');
        const label = ROUTE_LABELS[segment] ?? segment;
        const isLast = index === segments.length - 1;

        return (
          <span key={href} className="flex items-center gap-1">
            {index > 0 && (
              <ChevronRight
                size={12}
                style={{ color: 'var(--text-disabled)' }}
              />
            )}
            {isLast ? (
              <span
                className="font-medium"
                style={{ color: 'var(--text-primary)' }}
              >
                {label}
              </span>
            ) : (
              <Link
                href={href}
                className="transition-colors hover:text-white"
                style={{ color: 'var(--text-tertiary)' }}
              >
                {label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
