import type { Metadata } from 'next';
import { Sidebar } from '@/components/layout/sidebar';
import { Header } from '@/components/layout/header';
import { MobileNavigation } from '@/components/layout/mobile-navigation';

export const metadata: Metadata = {
  title: {
    default: 'Dashboard',
    template: '%s — AI Code Reviewer',
  },
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="app-shell">
      {/* Sidebar — hidden on mobile */}
      <div className="hidden md:flex">
        <Sidebar />
      </div>

      {/* Main area */}
      <div className="app-main">
        {/* Header */}
        <header className="app-header">
          {/* Mobile nav trigger */}
          <div className="md:hidden">
            <MobileNavigation />
          </div>
          <Header />
        </header>

        {/* Page content */}
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
