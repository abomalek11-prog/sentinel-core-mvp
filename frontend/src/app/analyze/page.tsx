'use client';

import { Suspense, useEffect, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { useAnalysisStore } from '@/lib/store';
import { AnalyzeToolbar } from '@/components/analyze/AnalyzeToolbar';
import { PipelineProgress } from '@/components/analyze/PipelineProgress';
import { ResultsPanel } from '@/components/analyze/ResultsPanel';

const EditorPanel = dynamic(
  () => import('@/components/analyze/EditorPanel').then(m => ({ default: m.EditorPanel })),
  { ssr: false, loading: () => (
    <div className="flex items-center justify-center h-full rounded-2xl border border-border" style={{ background: 'var(--color-deep)' }}>
      <span className="text-text-ghost text-sm font-mono">Loading editor…</span>
    </div>
  )}
);

const CustomCursor = dynamic(
  () => import('@/components/ui/CustomCursor').then(m => ({ default: m.CustomCursor })),
  { ssr: false }
);

function DemoTrigger() {
  const searchParams = useSearchParams();
  const loadDemoAndRun = useAnalysisStore((s) => s.loadDemoAndRun);
  const triggered = useRef(false);

  useEffect(() => {
    if (searchParams.get('demo') === '1' && !triggered.current) {
      triggered.current = true;
      loadDemoAndRun();
    }
  }, [searchParams, loadDemoAndRun]);

  return null;
}

export default function AnalyzePage() {
  return (
    <div className="h-screen flex flex-col overflow-hidden relative" style={{ background: 'var(--color-void)' }}>
      <Suspense fallback={null}>
        <DemoTrigger />
      </Suspense>
      <CustomCursor />
      <div className="pointer-events-none absolute inset-0 opacity-70" style={{ background: 'radial-gradient(1200px 600px at 15% -10%, rgba(30,144,176,0.14), transparent 60%), radial-gradient(800px 500px at 100% 0%, rgba(255,196,77,0.08), transparent 65%)' }} />
      <AnalyzeToolbar />

      {/* Main split */}
      <div className="flex-1 flex flex-col xl:flex-row min-h-0 gap-0 relative z-10">
        {/* Editor — left */}
        <div className="xl:basis-[58%] min-h-0 flex flex-col p-3">
          <div className="mb-3">
            <PipelineProgress />
          </div>
          <div className="flex-1 min-h-0 relative">
            <EditorPanel />
          </div>
        </div>

        {/* Results — right */}
        <div className="xl:basis-[42%] min-h-0 p-3 xl:pl-0">
          <ResultsPanel />
        </div>
      </div>
    </div>
  );
}
