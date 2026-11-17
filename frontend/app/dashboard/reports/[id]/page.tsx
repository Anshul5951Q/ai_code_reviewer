import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ReviewReportView } from './review-report-view';

export const metadata: Metadata = {
  title: 'Review Report',
};

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ReviewReportPage({ params }: Props) {
  const resolvedParams = await params;
  const id = resolvedParams?.id;

  if (!id || typeof id !== 'string' || id.trim() === '' || id === 'undefined') {
    notFound();
  }

  return <ReviewReportView reviewId={id.trim()} />;
}
