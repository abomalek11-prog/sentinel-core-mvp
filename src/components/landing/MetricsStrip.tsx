'use client';

const METRICS = [
  { value: '3.2M',   label: 'CVEs Analyzed' },
  { value: '99.97%', label: 'Patch Accuracy' },
  { value: '< 2s',   label: 'Detection Time' },
  { value: 'Zero',   label: 'False Positives' },
  { value: 'SOC2',   label: 'Compliant' },
];

export function MetricsStrip() {
  const items = [...METRICS, ...METRICS];
  return (
    <section className="relative border-y border-border overflow-hidden" style={{ background: '#060C14' }}>
      <div className="flex animate-marquee whitespace-nowrap py-5">
        {items.map((m, i) => (
          <span key={i} className="flex items-center gap-3 mx-8 shrink-0">
            <span className="text-teal-bright font-display font-semibold text-sm tracking-wide">{m.value}</span>
            <span className="text-text-ghost text-xs font-body">{m.label}</span>
            <span className="text-amber text-[10px] mx-4">✦</span>
          </span>
        ))}
      </div>
    </section>
  );
}
