'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  GitBranch,
  ScanSearch,
  ClipboardList,
  FileText,
  ShieldAlert,
  Settings,
  Code2,
  Menu,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Repositories', href: '/dashboard/repositories', icon: GitBranch },
  { label: 'Reviewer', href: '/dashboard/reviewer', icon: ScanSearch },
  { label: 'Reviews', href: '/dashboard/reviews', icon: ClipboardList },
  { label: 'Reports', href: '/dashboard/reports', icon: FileText },
  { label: 'Security', href: '/dashboard/security', icon: ShieldAlert },
  { label: 'Settings', href: '/dashboard/settings', icon: Settings },
] as const;

export function MobileNavigation() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/dashboard') return pathname === '/dashboard';
    return pathname.startsWith(href);
  };

  return (
    <>
      {/* Trigger */}
      <button
        onClick={() => setOpen(true)}
        className="p-1.5 rounded transition-colors hover:bg-white/5"
        style={{ color: 'var(--text-secondary)' }}
        aria-label="Open navigation"
        aria-expanded={open}
      >
        <Menu size={18} />
      </button>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Drawer */}
      <aside
        className={cn(
          'fixed left-0 top-0 bottom-0 z-50 flex flex-col w-64 transition-transform duration-250',
        )}
        style={{
          background: 'var(--bg-surface)',
          borderRight: '1px solid var(--border-subtle)',
          transform: open ? 'translateX(0)' : 'translateX(-100%)',
        }}
        aria-hidden={!open}
      >
        <div
          className="flex items-center justify-between px-4 py-4 border-b"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <div className="flex items-center gap-2.5">
            <Code2 size={16} style={{ color: 'var(--primary)' }} />
            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Code Reviewer
            </span>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="p-1 rounded transition-colors hover:bg-white/5"
            style={{ color: 'var(--text-secondary)' }}
            aria-label="Close navigation"
          >
            <X size={16} />
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2 rounded text-[13px] font-medium transition-colors"
                style={
                  active
                    ? { background: 'var(--primary-subtle)', color: 'var(--primary-hover)' }
                    : { color: 'var(--text-secondary)' }
                }
              >
                <Icon size={15} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
