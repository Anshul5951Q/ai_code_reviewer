import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'AI Code Reviewer',
    template: '%s — AI Code Reviewer',
  },
  description:
    'AI-powered code review and security analysis platform. ' +
    'Identify vulnerabilities, improve code quality, and accelerate remediation.',
  keywords: ['code review', 'security analysis', 'AI', 'developer tools'],
  robots: 'noindex, nofollow', // Development phase — not public
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
