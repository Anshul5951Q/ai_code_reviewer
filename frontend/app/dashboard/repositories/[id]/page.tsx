import type { Metadata } from 'next';
import { RepositoryDetailView } from './repository-detail-view';

export const metadata: Metadata = {
  title: 'Repository Details',
};

interface Props {
  params: Promise<{ id: string }>;
}

export default async function RepositoryDetailPage({ params }: Props) {
  const { id } = await params;
  return <RepositoryDetailView repositoryId={id} />;
}
