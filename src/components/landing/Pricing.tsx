'use client';

import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { Check } from 'lucide-react';
import { MagneticButton } from '@/components/ui/MagneticButton';

const TIERS = [
  {
    name: 'Open Source',
    price: 'Free',
    desc: 'For individual developers and open-source projects.',
    features: [
      'CPG analysis up to 10K LOC',
      '3 scans per day',
      'Community support',
      'Basic vulnerability detection',
      'CLI access',
    ],
    cta: 'Get Started',
    highlight: false,
  },
  {
    name: 'Pro',
    price: '$49',
    period: '/mo',
    desc: 'For teams shipping secure code every sprint.',
    features: [
      'Unlimited CPG analysis',
      'Unlimited scans',
      'Automated patching',
      'Priority support',
      'CI/CD integrations',
      'Custom rules engine',
      'Team dashboards',
    ],
    cta: 'Start Free Trial',
    highlight: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    desc: 'For organizations that need full control.',
    features: [
      'Everything in Pro',
      'On-premise deployment',
      'SOC2 & FedRAMP compliance',
      'SSO / SAML / RBAC',
      'Dedicated account manager',
      'SLA guarantee',
      'Custom integrations',
    ],
    cta: 'Contact Sales',
    highlight: false,
  },
];

export function Pricing() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section id="pricing" className="py-32 relative overflow-hidden" style={{ background: 'var(--color-deep)' }}>
      <div className="max-w-screen-xl mx-auto px-6 md:px-12">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="text-center mb-20"
        >
          <p className="label-mono mb-4">— Pricing</p>
          <h2 className="font-display font-light text-4xl md:text-5xl text-text-primary" style={{ letterSpacing: '-0.03em' }}>
            Start Free. Scale Securely.
          </h2>
        </motion.div>

        <div ref={ref} className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {TIERS.map((tier, i) => (
            <motion.div
              key={tier.name}
              initial={{ opacity: 0, y: 40 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.12 * i }}
              className={`relative rounded-2xl border p-8 flex flex-col ${
                tier.highlight
                  ? 'border-teal bg-surface shadow-[0_0_60px_rgba(30,144,176,0.08)]'
                  : 'border-border bg-surface'
              }`}
            >
              {tier.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-teal text-void text-[10px] font-display font-bold px-3 py-1 rounded-full tracking-widest uppercase">
                    Most Popular
                  </span>
                </div>
              )}

              <h3 className="font-display font-medium text-lg text-text-primary mb-2">{tier.name}</h3>
              <p className="text-text-muted text-sm mb-6">{tier.desc}</p>

              <div className="mb-8">
                <span className="font-display text-4xl font-light text-text-primary">{tier.price}</span>
                {tier.period && <span className="text-text-muted text-sm">{tier.period}</span>}
              </div>

              <ul className="space-y-3 mb-8 flex-1">
                {tier.features.map(f => (
                  <li key={f} className="flex items-start gap-3 text-sm text-text-muted">
                    <Check size={14} className="text-teal mt-0.5 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>

              <MagneticButton className={tier.highlight ? 'btn-primary w-full' : 'btn-secondary w-full'}>
                {tier.cta}
              </MagneticButton>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="section-number">06</div>
    </section>
  );
}
