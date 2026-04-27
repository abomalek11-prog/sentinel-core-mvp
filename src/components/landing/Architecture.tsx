'use client';

import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';

const NODES = [
  { id: 'ingest',    label: 'Ingest',        x: 80,   y: 140 },
  { id: 'parser',    label: 'Tree-sitter',   x: 230,  y: 80 },
  { id: 'cpg',       label: 'CPG Engine',    x: 380,  y: 140 },
  { id: 'gnn',       label: 'GNN Model',     x: 530,  y: 80 },
  { id: 'llm',       label: 'LLM Agents',    x: 530,  y: 200 },
  { id: 'patch',     label: 'Patch Engine',  x: 680,  y: 140 },
  { id: 'sandbox',   label: 'Sandbox',       x: 830,  y: 140 },
  { id: 'deploy',    label: 'Deploy',        x: 980,  y: 140 },
];

const EDGES: [string, string][] = [
  ['ingest', 'parser'],
  ['parser', 'cpg'],
  ['cpg', 'gnn'],
  ['cpg', 'llm'],
  ['gnn', 'patch'],
  ['llm', 'patch'],
  ['patch', 'sandbox'],
  ['sandbox', 'deploy'],
];

function getNode(id: string) {
  return NODES.find(n => n.id === id)!;
}

export function Architecture() {
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
          <p className="label-mono mb-4">— Architecture</p>
          <h2 className="font-display font-light text-4xl md:text-5xl text-text-primary" style={{ letterSpacing: '-0.03em' }}>
            Under the Hood
          </h2>
        </motion.div>

        <motion.div
          ref={ref}
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ duration: 1, delay: 0.3 }}
          className="overflow-x-auto pb-4"
        >
          <svg viewBox="0 0 1060 280" className="w-full min-w-[700px] max-w-4xl mx-auto" fill="none">
            {/* Edges */}
            {EDGES.map(([fromId, toId], i) => {
              const from = getNode(fromId);
              const to   = getNode(toId);
              return (
                <line
                  key={i}
                  x1={from.x} y1={from.y}
                  x2={to.x}   y2={to.y}
                  stroke="var(--color-border)"
                  strokeWidth="1.5"
                  strokeDasharray="6 4"
                  className={inView ? 'flow-line' : ''}
                />
              );
            })}

            {/* Nodes */}
            {NODES.map((node, i) => {
              const isHeal = node.id === 'patch' || node.id === 'deploy';
              return (
                <motion.g
                  key={node.id}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={inView ? { opacity: 1, scale: 1 } : {}}
                  transition={{ duration: 0.6, delay: 0.1 * i }}
                >
                  <rect
                    x={node.x - 50} y={node.y - 20}
                    width={100} height={40} rx={12}
                    fill="var(--color-surface)"
                    stroke={isHeal ? 'var(--color-amber)' : 'var(--color-border)'}
                    strokeWidth={1}
                  />
                  <text
                    x={node.x} y={node.y + 5}
                    textAnchor="middle"
                    fill={isHeal ? 'var(--color-amber)' : 'var(--color-teal)'}
                    fontSize="11"
                    fontFamily="var(--font-display)"
                  >
                    {node.label}
                  </text>
                </motion.g>
              );
            })}
          </svg>
        </motion.div>
      </div>

      <div className="section-number">05</div>
    </section>
  );
}
