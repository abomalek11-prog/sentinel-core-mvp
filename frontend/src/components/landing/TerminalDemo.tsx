'use client';

import { useRef, useState, useEffect } from 'react';
import { motion, useInView } from 'framer-motion';

const TERMINAL_LINES = [
  { text: '$ netra scan --target ./src --deep', color: 'text-teal-dim', delay: 0 },
  { text: '▸ Initializing CPG engine...', color: 'text-teal-dim', delay: 400 },
  { text: '▸ Parsing 847 source files', color: 'text-teal-bright', delay: 800 },
  { text: '▸ Building code property graph... done (2.3s)', color: 'text-teal-dim', delay: 1400 },
  { text: '▸ Running AI vulnerability detection', color: 'text-teal-bright', delay: 2000 },
  { text: '', color: '', delay: 2400 },
  { text: '  ✗ CRITICAL: SQL Injection in auth/login.py:42', color: 'text-red-400', delay: 2600 },
  { text: '  ✗ HIGH: Command Injection in utils/exec.py:18', color: 'text-red-400', delay: 3000 },
  { text: '  ✗ MEDIUM: Unsafe Deserialization in data/load.py:91', color: 'text-amber', delay: 3400 },
  { text: '', color: '', delay: 3600 },
  { text: '▸ PATCHING auth/login.py:42 ...', color: 'text-amber', delay: 3800 },
  { text: '  ✓ HEALED — parameterized query applied', color: 'text-emerald-400', delay: 4400 },
  { text: '▸ PATCHING utils/exec.py:18 ...', color: 'text-amber', delay: 4800 },
  { text: '  ✓ HEALED — subprocess.run with shell=False', color: 'text-emerald-400', delay: 5400 },
  { text: '▸ PATCHING data/load.py:91 ...', color: 'text-amber', delay: 5800 },
  { text: '  ✓ HEALED — safe loader substituted', color: 'text-emerald-400', delay: 6400 },
  { text: '', color: '', delay: 6600 },
  { text: '▸ All patches verified in sandbox ✓', color: 'text-teal-bright', delay: 6800 },
  { text: '▸ Confidence: 99.2% | Time: 1.87s | 3/3 healed', color: 'text-teal', delay: 7200 },
];

function AnimatedTerminal({ active }: { active: boolean }) {
  const [visibleLines, setVisibleLines] = useState(0);

  useEffect(() => {
    if (!active) return;
    setVisibleLines(0);
    const timers: ReturnType<typeof setTimeout>[] = [];
    TERMINAL_LINES.forEach((line, i) => {
      timers.push(setTimeout(() => setVisibleLines(i + 1), line.delay));
    });
    // Loop
    const loop = setTimeout(() => setVisibleLines(0), 9000);
    timers.push(loop);
    const restart = setTimeout(() => {
      if (active) {
        setVisibleLines(0);
        TERMINAL_LINES.forEach((line, i) => {
          timers.push(setTimeout(() => setVisibleLines(i + 1), line.delay));
        });
      }
    }, 9500);
    timers.push(restart);
    return () => timers.forEach(clearTimeout);
  }, [active]);

  return (
    <div className="crt rounded-2xl border border-border overflow-hidden" style={{ background: 'var(--color-surface)' }}>
      {/* Chrome */}
      <div className="flex items-center gap-2 px-5 py-3.5 border-b border-border">
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-red-500/70" />
          <div className="w-3 h-3 rounded-full bg-amber/70" />
          <div className="w-3 h-3 rounded-full bg-emerald-500/70" />
        </div>
        <span className="flex-1 text-center text-[10px] text-text-ghost font-mono">netra-cli — scan</span>
      </div>

      {/* Terminal body */}
      <div className="p-5 font-mono text-xs leading-relaxed min-h-[320px] relative">
        <div className="scan-line" />
        {TERMINAL_LINES.slice(0, visibleLines).map((line, i) => (
          <div key={i} className={`${line.color} ${!line.text ? 'h-3' : ''}`}>
            {line.text}
          </div>
        ))}
        {visibleLines < TERMINAL_LINES.length && (
          <span className="inline-block w-2 h-4 bg-teal animate-blink" />
        )}
      </div>
    </div>
  );
}

const STAT_CARDS = [
  { label: 'Vulnerabilities Found', value: '3', badge: 'bg-red-500/10 text-red-400 border-red-500/20' },
  { label: 'Auto-patched', value: '3/3', badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  { label: 'Time Elapsed', value: '1.87s', badge: 'bg-teal/10 text-teal border-teal/20' },
  { label: 'Confidence', value: '99.2%', badge: 'bg-amber/10 text-amber border-amber/20' },
];

export function TerminalDemo() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section className="py-32 relative overflow-hidden">
      <div className="max-w-screen-xl mx-auto px-6 md:px-12">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="text-center mb-16"
        >
          <p className="label-mono mb-4">— Live Demo</p>
          <h2 className="font-display font-light text-4xl md:text-5xl text-text-primary" style={{ letterSpacing: '-0.03em' }}>
            Watch Netra Heal
          </h2>
        </motion.div>

        <div ref={ref} className="grid grid-cols-1 lg:grid-cols-5 gap-8 items-start">
          {/* Terminal (60%) */}
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
            className="lg:col-span-3"
          >
            <AnimatedTerminal active={inView} />
          </motion.div>

          {/* Stats (40%) */}
          <div className="lg:col-span-2 space-y-4">
            {STAT_CARDS.map((card, i) => (
              <motion.div
                key={card.label}
                initial={{ opacity: 0, x: 30 }}
                animate={inView ? { opacity: 1, x: 0 } : {}}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.15 * i + 0.5 }}
                className="glass-card rounded-xl p-5 flex items-center justify-between"
              >
                <span className="text-text-muted text-sm">{card.label}</span>
                <span className={`px-3 py-1 rounded-full border text-sm font-mono font-medium ${card.badge}`}>
                  {card.value}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      <div className="section-number">03</div>
    </section>
  );
}
