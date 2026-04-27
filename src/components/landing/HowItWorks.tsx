'use client';

import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { Database, Eye, GitBranch, Zap } from 'lucide-react';

const STEPS = [
  {
    num: '01',
    label: 'Ingest',
    title: 'Parse & Build CPG',
    desc: 'Parse entire codebase into a live Code Property Graph in under 4 seconds.',
    Icon: Database,
    color: '#1E90B0',
  },
  {
    num: '02',
    label: 'Perceive',
    title: 'Detect Anomalies',
    desc: 'AI models detect zero-days, logic flaws, and dependency risks in real-time.',
    Icon: Eye,
    color: '#1E90B0',
  },
  {
    num: '03',
    label: 'Reason',
    title: 'Trace Exploit Paths',
    desc: 'Traces vulnerability paths across thousands of code nodes using the CPG.',
    Icon: GitBranch,
    color: '#1E90B0',
  },
  {
    num: '04',
    label: 'Heal',
    title: 'Auto-Patch and Verify',
    desc: 'Automated patch generation, validation, and deployment with full audit trail.',
    Icon: Zap,
    color: '#FFC44D',
  },
];

export function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-120px' });

  return (
    <section id="how-it-works" className="py-32 relative overflow-hidden" style={{ background: 'var(--color-deep)' }}>
      <div className="max-w-screen-xl mx-auto px-6 md:px-12">
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: 40 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="text-center mb-20"
        >
          <p className="label-mono mb-4">— How It Works</p>
          <h2 className="font-display font-light text-4xl md:text-5xl text-text-primary" style={{ letterSpacing: '-0.03em' }}>
            The Netra Intelligence Loop
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 relative">
          {/* Connecting line (desktop) */}
          <div className="hidden md:block absolute top-16 left-[12.5%] right-[12.5%] h-px">
            <svg width="100%" height="2" className="overflow-visible">
              <line
                x1="0" y1="1" x2="100%" y2="1"
                stroke="var(--color-border)"
                strokeWidth="1"
                strokeDasharray="6 4"
                className={inView ? 'flow-line' : ''}
              />
            </svg>
          </div>

          {STEPS.map((step, i) => (
            <motion.div
              key={step.num}
              initial={{ opacity: 0, y: 40 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.12 * i }}
              className="relative text-center group"
            >
              {/* Icon circle */}
              <div
                className="w-14 h-14 rounded-2xl border border-border flex items-center justify-center mx-auto mb-6 transition-all duration-300 group-hover:border-teal-dim"
                style={{ background: 'var(--color-surface)' }}
              >
                <step.Icon size={22} style={{ color: step.color }} />
              </div>

              {/* Number */}
              <div
                className="font-display text-xs tracking-widest mb-2 transition-colors duration-300"
                style={{ color: inView ? step.color : 'var(--color-text-ghost)' }}
              >
                {step.num}
              </div>

              <h3 className="font-display font-medium text-lg text-text-primary mb-2">{step.title}</h3>
              <p className="text-text-muted text-sm leading-relaxed max-w-[200px] mx-auto">{step.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="section-number">02</div>
    </section>
  );
}
