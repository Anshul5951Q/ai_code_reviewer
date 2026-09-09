import type { Metadata } from 'next';
import { GitMerge, ScanSearch, Sliders } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';

export const metadata: Metadata = {
  title: 'Settings',
};

interface SettingsSectionProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}

function SettingsSection({ icon, title, description, children }: SettingsSectionProps) {
  return (
    <section className="card mb-4">
      <div className="flex items-start gap-3 mb-4 pb-4" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <div
          className="w-8 h-8 rounded flex items-center justify-center flex-shrink-0"
          style={{ background: 'var(--bg-elevated)' }}
        >
          <span style={{ color: 'var(--text-tertiary)' }}>{icon}</span>
        </div>
        <div>
          <h2 className="text-[14px] font-semibold" style={{ color: 'var(--text-primary)' }}>
            {title}
          </h2>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
            {description}
          </p>
        </div>
      </div>
      {children}
    </section>
  );
}

interface SettingsRowProps {
  label: string;
  description?: string;
  control: React.ReactNode;
}

function SettingsRow({ label, description, control }: SettingsRowProps) {
  return (
    <div className="flex items-center justify-between gap-6 py-2.5" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <div>
        <p className="text-[13px] font-medium" style={{ color: 'var(--text-primary)' }}>
          {label}
        </p>
        {description && (
          <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
            {description}
          </p>
        )}
      </div>
      <div className="flex-shrink-0">{control}</div>
    </div>
  );
}

function DisabledToggle({ label }: { label: string }) {
  return (
    <div
      className="w-8 h-4 rounded-full relative cursor-not-allowed"
      style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)' }}
      title="Not configurable in Phase 1"
      aria-label={label}
    >
      <span
        className="absolute left-0.5 top-0.5 w-3 h-3 rounded-full"
        style={{ background: 'var(--text-disabled)' }}
      />
    </div>
  );
}

function ComingSoonBadge() {
  return (
    <span
      className="inline-flex px-2 py-0.5 rounded text-[11px] font-medium"
      style={{
        background: 'var(--primary-subtle)',
        color: 'var(--primary-hover)',
        border: '1px solid var(--primary-border)',
      }}
    >
      Coming in Phase 3
    </span>
  );
}

export default function SettingsPage() {
  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Settings"
        description="Configure application behavior and integrations."
      />

      {/* Application Preferences */}
      <SettingsSection
        icon={<Sliders size={15} />}
        title="Application Preferences"
        description="General UI and application behavior settings."
      >
        <SettingsRow
          label="Theme"
          description="Interface color scheme"
          control={
            <span className="text-[12px] font-medium" style={{ color: 'var(--text-secondary)' }}>
              Dark (default)
            </span>
          }
        />
        <SettingsRow
          label="Compact mode"
          description="Reduce spacing for denser information display"
          control={<DisabledToggle label="Compact mode toggle" />}
        />
        <SettingsRow
          label="Reduced motion"
          description="Respect system accessibility preferences"
          control={
            <span className="text-[12px]" style={{ color: 'var(--text-tertiary)' }}>
              Follows OS setting
            </span>
          }
        />
      </SettingsSection>

      {/* Analysis Preferences */}
      <SettingsSection
        icon={<ScanSearch size={15} />}
        title="Analysis Preferences"
        description="Default configuration for new analysis runs."
      >
        <SettingsRow
          label="Default analysis scope"
          description="Modules enabled by default on new reviews"
          control={
            <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
              All modules
            </span>
          }
        />
        <SettingsRow
          label="Minimum confidence threshold"
          description="Findings below this confidence score are filtered out"
          control={
            <span className="text-[12px] font-mono" style={{ color: 'var(--text-secondary)' }}>
              70%
            </span>
          }
        />
        <SettingsRow
          label="Auto-remediation suggestions"
          description="Generate fix suggestions alongside findings"
          control={<DisabledToggle label="Auto-remediation toggle" />}
        />
      </SettingsSection>

      {/* GitHub Integration */}
      <SettingsSection
        icon={<GitMerge size={15} />}
        title="GitHub Integration"
        description="Connect your GitHub account to import repositories."
      >
        <SettingsRow
          label="GitHub Account"
          description="Connect via OAuth to access your repositories"
          control={<ComingSoonBadge />}
        />
        <SettingsRow
          label="Repository access"
          description="Control which repositories are accessible for analysis"
          control={<ComingSoonBadge />}
        />
        <SettingsRow
          label="Webhook integration"
          description="Trigger analysis automatically on push events"
          control={<ComingSoonBadge />}
        />
      </SettingsSection>
    </div>
  );
}
