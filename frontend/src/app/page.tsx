'use client';

import dynamic from 'next/dynamic';
import { Navbar } from '@/components/landing/Navbar';
import { Hero } from '@/components/landing/Hero';
import { MetricsStrip } from '@/components/landing/MetricsStrip';
import { HowItWorks } from '@/components/landing/HowItWorks';
import { TerminalDemo } from '@/components/landing/TerminalDemo';
import { FeatureGrid } from '@/components/landing/FeatureGrid';
import { Architecture } from '@/components/landing/Architecture';
import { Pricing } from '@/components/landing/Pricing';
import { Footer } from '@/components/landing/Footer';

const CustomCursor = dynamic(
  () => import('@/components/ui/CustomCursor').then(m => ({ default: m.CustomCursor })),
  { ssr: false }
);

const LoadingScreen = dynamic(
  () => import('@/components/ui/LoadingScreen').then(m => ({ default: m.LoadingScreen })),
  { ssr: false }
);

export default function HomePage() {
  return (
    <>
      <LoadingScreen />
      <CustomCursor />
      <Navbar />
      <main>
        <Hero />
        <MetricsStrip />
        <HowItWorks />
        <TerminalDemo />
        <FeatureGrid />
        <Architecture />
        <Pricing />
      </main>
      <Footer />
    </>
  );
}
