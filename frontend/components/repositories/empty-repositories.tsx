import { GitBranch } from 'lucide-react';
import { EmptyState } from '@/components/common/empty-state';
import { ConnectGithub } from './connect-github';

interface EmptyRepositoriesProps {
  onRepositoryImported?: () => void;
}

export function EmptyRepositories({ onRepositoryImported }: EmptyRepositoriesProps) {
  return (
    <EmptyState
      icon={<GitBranch size={20} />}
      title="No repositories connected"
      description="Connect GitHub to import your repositories and start your first code review."
      action={<ConnectGithub variant="button" onRepositoryImported={onRepositoryImported} />}
      className="py-20"
    />
  );
}
