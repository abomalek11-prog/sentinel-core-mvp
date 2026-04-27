import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Netra — Security Analysis and Patching',
  description: 'Static analysis, vulnerability detection, and automated secure code patching.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className="antialiased">
        <div className="noise-overlay" aria-hidden="true" />
        {children}
      </body>
    </html>
  );
}
