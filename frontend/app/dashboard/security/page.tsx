import type { Metadata } from 'next';
import { SecurityView } from './security-view';

export const metadata: Metadata = {
  title: 'Security',
};

export default function SecurityPage() {
  return <SecurityView />;
}
