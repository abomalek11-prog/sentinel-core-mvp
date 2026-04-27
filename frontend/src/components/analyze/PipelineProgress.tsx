'use client';

import { useAnalysisStore } from '@/lib/store';
import type { PipelineStage } from '@/types/sentinel';

const STAGES: { key: PipelineStage; label: string }[] = [
  { key: 'parsing',      label: 'Parse' },
  { key: 'building_cpg', label: 'CPG' },
  { key: 'detecting',    label: 'Detect' },
  { key: 'reasoning',    label: 'Reason' },
  { key: 'patching',     label: 'Patch' },
  { key: 'verifying',    label: 'Verify' },
];

function stageIndex(s: PipelineStage): number {
  const idx = STAGES.findIndex(st => st.key === s);
  if (s === 'done') return STAGES.length;
  if (s === 'error') return -1;
  return idx;
}

export function PipelineProgress() {
  const { stage, statusMessage, cpgNodes, cpgEdges } = useAnalysisStore();
  const currentIdx = stageIndex(stage);

  if (stage === 'idle') return null;

  return (
    <div className="glass-card rounded-xl p-4">
      {/* Stage indicators */}
      <div className="flex items-center gap-1 mb-3">
        {STAGES.map((s, i) => {
          const isActive  = i === currentIdx;
          const isDone    = i < currentIdx || stage === 'done';
          const isError   = stage === 'error' && i === currentIdx;

          return (
            <div key={s.key} className="flex-1 flex flex-col items-center gap-1.5">
              <div
                className={`h-1 w-full rounded-full transition-all duration-500 ${
                  isDone   ? 'bg-teal' :
                  isActive ? 'bg-teal animate-pulse' :
                  isError  ? 'bg-red-500' :
                  'bg-border'
                }`}
              />
              <span className={`text-[9px] font-mono tracking-widest uppercase transition-colors ${
                isActive || isDone ? 'text-teal' : 'text-text-ghost'
              }`}>
                {s.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Status message */}
      <div className="flex items-center justify-between">
        <span className="text-text-muted text-xs font-mono">{statusMessage}</span>
        {cpgNodes > 0 && (
          <span className="text-text-ghost text-[10px] font-mono">
            {cpgNodes} nodes · {cpgEdges} edges
          </span>
        )}
      </div>
    </div>
  );
}
