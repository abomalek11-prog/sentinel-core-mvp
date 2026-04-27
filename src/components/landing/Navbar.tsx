'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion, useScroll, useTransform } from 'framer-motion';
import { NetraLogo } from '@/components/logo/NetraLogo';
import { MagneticButton } from '@/components/ui/MagneticButton';

const NAV_LINKS = [
  { href: '#how-it-works', label: 'How It Works' },
  { href: '#features',     label: 'Features' },
  { href: '#pricing',      label: 'Pricing' },
];

export function Navbar() {
  const { scrollY } = useScroll();
  const borderOpacity = useTransform(scrollY, [0, 100], [0, 1]);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const unsub = scrollY.on('change', v => setScrolled(v > 60));
    return unsub;
  }, [scrollY]);

  return (
    <motion.header
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
      className="fixed top-0 inset-x-0 z-[100] px-6 md:px-12 py-4"
    >
      <div className="glass rounded-2xl px-6 py-3 flex items-center justify-between max-w-screen-xl mx-auto relative">
        {/* Border bottom on scroll */}
        <motion.div
          className="absolute inset-x-0 bottom-0 h-px"
          style={{
            opacity: borderOpacity,
            background: 'linear-gradient(90deg, transparent, var(--color-teal-dim), transparent)',
          }}
        />

        {/* Logo */}
        <Link href="/">
          <NetraLogo variant="full" size={28} animated />
        </Link>

        {/* Center nav links */}
        <nav className="hidden md:flex items-center gap-8">
          {NAV_LINKS.map(link => (
            <a
              key={link.href}
              href={link.href}
              className="relative text-xs tracking-[0.08em] text-text-muted hover:text-text-primary transition-colors duration-200 py-1 group"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              {link.label}
              <span className="absolute bottom-0 left-0 h-px w-0 group-hover:w-full transition-all duration-300 bg-teal" />
            </a>
          ))}
        </nav>

        {/* CTA */}
        <MagneticButton
          className="btn-secondary !py-2 !px-5 !text-xs !rounded-full group"
          as="a"
          href="/analyze"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-teal group-hover:bg-amber transition-colors duration-300" />
          Request Access
        </MagneticButton>
      </div>
    </motion.header>
  );
}
