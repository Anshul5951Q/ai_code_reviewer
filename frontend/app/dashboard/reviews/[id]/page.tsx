import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ReviewDetailView } from './review-detail-view';

export const metadata: Metadata = {
  title: 'Review Details',
};

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ReviewDetailPage({ params }: Props) {
  const resolvedParams = await params;
  const id = resolvedParams?.id;

  if (!id || typeof id !== 'string' || id.trim() === '' || id === 'undefined') {
    notFound();
  }

  return <ReviewDetailView reviewId={id.trim()} />;
}
