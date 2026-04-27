'use client';

import { useEffect, useRef, useState, Suspense } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MagneticButton } from '@/components/ui/MagneticButton';
import { Play, ChevronDown } from 'lucide-react';
import dynamic from 'next/dynamic';

const HeroScene = dynamic(
  () => import('@/components/three/HeroScene').then(m => ({ default: m.HeroScene })),
  { ssr: false }
);

const OVERLINE = 'SECURITY · ANALYSIS · PATCHING';

function TypewriterOverline() {
  const [text, setText] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  useEffect(() => {
    let i = 0;
    const delay = setTimeout(() => {
      const interval = setInterval(() => {
        setText(OVERLINE.slice(0, i + 1));
        i++;
        if (i >= OVERLINE.length) {
          clearInterval(interval);
          setTimeout(() => setShowCursor(false), 1500);
        }
      }, 40);
      return () => clearInterval(interval);
    }, 1200);
    return () => clearTimeout(delay);
  }, []);
  return (
    <span className="label-mono !text-teal-dim !tracking-[0.4em] !text-[10px]">
      {text}
      {showCursor && <span className="animate-blink ml-0.5">▊</span>}
    </span>
  );
}

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* 3D Background */}
      <Suspense fallback={null}>
        <HeroScene />
      </Suspense>

      {/* Subtle overlay for readability */}
      <div className="absolute inset-0 z-[1]" style={{
        background: 'radial-gradient(ellipse 60% 50% at 50% 50%, transparent, #040810 80%)',
      }} />

      {/* Content */}
      <div className="relative z-10 text-center px-6 max-w-4xl mx-auto">
        {/* Overline */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          className="mb-6"
        >
          <TypewriterOverline />
        </motion.div>

        {/* H1 — "Netra" */}
        <motion.h1
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
          className="text-gradient-hero font-display font-light leading-none mb-6"
          style={{ fontSize: 'clamp(5rem, 14vw, 9rem)', letterSpacing: '-0.03em' }}
        >
          Netra
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 1.2 }}
          className="text-hero-sub text-text-muted font-light max-w-2xl mx-auto mb-10"
        >
          Sees Every Vulnerability. Patches Before You Blink.
        </motion.p>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 1.6 }}
          className="flex flex-wrap items-center justify-center gap-4 mb-12"
        >
          <MagneticButton as="a" href="/analyze" className="btn-primary !rounded-full">
            Start Scanning
          </MagneticButton>
          <MagneticButton as="a" href="/analyze?demo=1" className="btn-secondary !rounded-full">
            <Play size={14} /> Watch Demo
          </MagneticButton>
        </motion.div>

        {/* Trust line */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 2 }}
          className="flex items-center justify-center gap-6"
        >
          <span className="text-text-ghost text-xs" style={{ fontFamily: 'var(--font-body)' }}>
            Trusted by 240+ security teams
          </span>
          <div className="flex items-center gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="w-16 h-6 rounded bg-border/30"
              />
            ))}
          </div>
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 2.5 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10"
      >
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        >
          <ChevronDown size={20} className="text-teal-dim" />
        </motion.div>
      </motion.div>

      {/* Section number */}
      <div className="section-number">01</div>
    </section>
  );
}
