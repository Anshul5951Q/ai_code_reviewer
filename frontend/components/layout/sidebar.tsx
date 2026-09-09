'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  GitBranch,
  ScanSearch,
  ClipboardList,
  ShieldAlert,
  Settings,
  Code2,
  Circle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_GROUPS = [
  {
    label: 'WORKSPACE',
    items: [
      { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
      { label: 'Repositories', href: '/dashboard/repositories', icon: GitBranch },
      { label: 'Reviewer', href: '/dashboard/reviewer', icon: ScanSearch },
      { label: 'Reviews', href: '/dashboard/reviews', icon: ClipboardList },
    ],
  },
  {
    label: 'SECURITY',
    items: [
      { label: 'Security', href: '/dashboard/security', icon: ShieldAlert },
    ],
  },
  {
    label: 'SYSTEM',
    items: [
      { label: 'Settings', href: '/dashboard/settings', icon: Settings },
    ],
  },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/dashboard') return pathname === '/dashboard';
    return pathname.startsWith(href);
  };

  return (
    <aside className="app-sidebar">
      {/* Logo */}
      <div
        className="flex items-center gap-2.5 px-4 py-4 border-b"
        style={{ borderColor: 'var(--border-subtle)' }}
      >
        <div
          className="w-7 h-7 rounded flex items-center justify-center flex-shrink-0"
          style={{ background: 'var(--primary-subtle)', border: '1px solid var(--primary-border)' }}
        >
          <Code2 size={14} style={{ color: 'var(--primary)' }} />
        </div>
        <span
          className="text-sm font-semibold tracking-wide uppercase"
          style={{ color: 'var(--text-primary)', letterSpacing: '0.06em' }}
        >
          Code Reviewer
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 space-y-5">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <p
              className="px-2 mb-1 text-[10px] font-semibold tracking-widest uppercase"
              style={{ color: 'var(--text-disabled)' }}
            >
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        'flex items-center gap-2.5 px-2 py-1.5 rounded text-[13px] font-medium transition-all duration-150',
                        active
                          ? 'text-white'
                          : 'hover:text-white'
                      )}
                      style={
                        active
                          ? {
                              background: 'var(--primary-subtle)',
                              color: 'var(--primary-hover)',
                              border: 'none',
                            }
                          : {
                              color: 'var(--text-secondary)',
                            }
                      }
                    >
                      <Icon size={14} style={{ flexShrink: 0 }} />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* System Status Footer */}
      <div
        className="px-4 py-3 border-t"
        style={{ borderColor: 'var(--border-subtle)' }}
      >
        <p className="text-[10px] font-semibold uppercase tracking-widest mb-1.5" style={{ color: 'var(--text-disabled)' }}>
          System Status
        </p>
        <div className="flex items-center gap-1.5">
          <Circle
            size={6}
            fill="var(--success)"
            style={{ color: 'var(--success)', flexShrink: 0 }}
          />
          <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
            Operational
          </span>
        </div>
      </div>
    </aside>
  );
}
