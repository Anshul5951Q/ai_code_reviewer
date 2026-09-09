import { ReviewDetailView } from './review-detail-view';

export default function ReviewDetailPage({ params }: { params: { id: string } }) {
  return <ReviewDetailView reviewId={params.id} />;
}
