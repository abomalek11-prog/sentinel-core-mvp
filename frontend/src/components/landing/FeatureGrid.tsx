'use client';

import { useRef, useCallback } from 'react';
import { motion, useInView } from 'framer-motion';
import { Network, ShieldAlert, Bot, MonitorCheck, FileSearch, Building2 } from 'lucide-react';

const FEATURES = [
  {
    Icon: Network,
    title: 'CPG Analysis',
    desc: 'Full code property graph construction in under 4 seconds. Maps data flow, control flow, and dependency edges.',
  },
  {
    Icon: ShieldAlert,
    title: 'Advanced Detection',
    desc: 'Pattern-agnostic analysis finds unknown vulnerability classes that rule-based scanners miss entirely.',
  },
  {
    Icon: Bot,
    title: 'Automated Patching',
    desc: 'Generates, tests, and applies safe patches with configurable approval gates. Six fix strategies, line-accurate diffs.',
  },
  {
    Icon: MonitorCheck,
    title: 'Continuous Vigilance',
    desc: 'Monitors 24/7 across every commit and dependency update. Real-time alerts, zero maintenance.',
  },
  {
    Icon: FileSearch,
    title: 'Detailed Analysis',
    desc: 'Full audit trail of every decision with reasoning chains. CWE classification and confidence scoring.',
  },
  {
    Icon: Building2,
    title: 'Enterprise Ready',
    desc: 'SOC2, GDPR, FedRAMP compliant with on-premise deployment. SSO, RBAC, and webhook integrations.',
  },
];

function FeatureCard({ feature, index, inView }: { feature: typeof FEATURES[0]; index: number; inView: boolean }) {
  const cardRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const card = cardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    card.style.setProperty('--mx', `${e.clientX - rect.left}px`);
    card.style.setProperty('--my', `${e.clientY - rect.top}px`);
  }, []);

  return (
    <motion.div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      initial={{ opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.08 * index }}
      className="card-glow relative rounded-2xl border border-border p-8 overflow-hidden group"
      style={{ background: 'var(--color-surface)' }}
    >
      {/* Spotlight follow */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{
          background: 'radial-gradient(400px circle at var(--mx, 50%) var(--my, 50%), rgba(30,144,176,0.06), transparent 40%)',
        }}
      />

      <div className="relative z-10">
        <div className="w-10 h-10 rounded-xl border border-border flex items-center justify-center mb-6 bg-deep group-hover:border-teal-dim transition-colors duration-300">
          <feature.Icon size={20} className="text-teal" />
        </div>
        <h3 className="font-display font-medium text-lg text-text-primary mb-3">{feature.title}</h3>
        <p className="text-text-muted text-sm leading-relaxed">{feature.desc}</p>
      </div>
    </motion.div>
  );
}

export function FeatureGrid() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section id="features" className="py-32 relative overflow-hidden" style={{ background: 'var(--color-deep)' }}>
      <div className="max-w-screen-xl mx-auto px-6 md:px-12">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="text-center mb-20"
        >
          <p className="label-mono mb-4">— Features</p>
          <h2 className="font-display font-light text-4xl md:text-5xl text-text-primary" style={{ letterSpacing: '-0.03em' }}>
            Built for Security Teams
          </h2>
        </motion.div>

        <div ref={ref} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((feature, i) => (
            <FeatureCard key={feature.title} feature={feature} index={i} inView={inView} />
          ))}
        </div>
      </div>

      <div className="section-number">04</div>
    </section>
  );
}
