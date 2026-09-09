import { RepositoryCard } from './repository-card';
import { EmptyRepositories } from './empty-repositories';
import type { Repository } from '@/types/repository';

interface RepositoryGridProps {
  repositories: Repository[];
  searchQuery: string;
  onRefresh?: () => void;
}

export function RepositoryGrid({ repositories, searchQuery, onRefresh }: RepositoryGridProps) {
  const filtered = searchQuery.trim()
  ? repositories.filter(
        (r) =>
          r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.owner.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.full_name.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : repositories;

  if (filtered.length === 0) {
    return <EmptyRepositories onRepositoryImported={onRefresh} />;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
      {filtered.map((repo) => (
        <RepositoryCard key={repo.id} repository={repo} onDeleted={onRefresh} />
      ))}
    </div>
  );
}
