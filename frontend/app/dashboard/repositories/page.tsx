import { Suspense } from 'react';
import type { Metadata } from 'next';
import { LoadingState } from '@/components/common/loading-state';
import { RepositoriesView } from './repositories-view';

export const metadata: Metadata = {
  title: 'Repositories',
};

export default function RepositoriesPage() {
  return (
    <Suspense fallback={<LoadingState message="Loading repositories..." />}>
      <RepositoriesView />
    </Suspense>
  );
}
