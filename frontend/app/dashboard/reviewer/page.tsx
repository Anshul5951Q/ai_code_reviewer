import { Suspense } from 'react';
import type { Metadata } from 'next';
import { LoadingState } from '@/components/common/loading-state';
import { ReviewerView } from './reviewer-view';

export const metadata: Metadata = {
  title: 'New Code Review',
};

export default function ReviewerPage() {
  return (
    <Suspense fallback={<LoadingState message="Loading reviewer options..." />}>
      <ReviewerView />
    </Suspense>
  );
}
