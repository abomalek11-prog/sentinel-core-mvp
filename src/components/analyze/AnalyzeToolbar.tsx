'use client';

import { useEffect, useState } from 'react';
import { useAnalysisStore } from '@/lib/store';
import { fetchDemo, fetchHealth } from '@/lib/api';
import { NetraLogo } from '@/components/logo/NetraLogo';
import { Play, Square, RotateCcw, Upload } from 'lucide-react';

export function AnalyzeToolbar() {
  const { stage, startAnalysis, cancelAnalysis, reset, setSourceCode, setFileName, llmModel } = useAnalysisStore();
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [model, setModel] = useState('');

  useEffect(() => {
    fetchHealth()
      .then(h => {
        setBackendUp(true);
        setModel(h.llm_model || '');
      })
      .catch(() => setBackendUp(false));
  }, []);

  const loadDemo = async () => {
    try {
      const demo = await fetchDemo();
      setSourceCode(demo.source_code);
      setFileName(demo.file_name);
    } catch {
      // ignore
    }
  };

  const isRunning = !['idle', 'done', 'error'].includes(stage);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 md:px-6 py-3 border-b border-border" style={{ background: 'linear-gradient(180deg, rgba(12,24,40,0.98), rgba(8,15,24,0.94))' }}>
      {/* Left: Logo + title */}
      <div className="flex items-center gap-3 min-w-0">
        <NetraLogo size={22} variant="icon" animated={false} />
        <span className="font-display text-sm text-text-primary font-medium tracking-tight">Analyzer Studio</span>
        <span className="text-text-ghost text-[10px]">|</span>

        {/* Backend status */}
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${
            backendUp === null ? 'bg-text-ghost animate-pulse' :
            backendUp ? 'bg-emerald-400' : 'bg-red-400'
          }`} />
          <span 
            className="text-[10px] font-mono text-text-ghost uppercase tracking-widest cursor-help"
            title={backendUp === false ? "Cannot reach the security backend. Ensure NEXT_PUBLIC_API_URL is configured correctly in production." : undefined}
          >
            {backendUp === null ? 'checking…' : backendUp ? 'connected' : 'offline'}
          </span>
        </div>

        {(llmModel || model) && (
          <>
            <span className="text-text-ghost text-[10px]">|</span>
            <span className="text-[10px] font-mono text-teal-dim truncate max-w-[170px]" title={llmModel || model}>{llmModel || model}</span>
          </>
        )}
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={loadDemo}
          disabled={isRunning}
          title="Load a vulnerable sample"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono text-text-muted border border-border hover:border-teal-dim hover:text-text-primary transition-all disabled:opacity-40"
        >
          <Upload size={12} />
          Demo
        </button>

        {stage === 'done' || stage === 'error' ? (
          <button
            onClick={reset}
            title="Clear analysis results and start fresh"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono text-text-muted border border-border hover:border-teal-dim hover:text-text-primary transition-all"
          >
            <RotateCcw size={12} />
            Reset
          </button>
        ) : null}

        {isRunning ? (
          <button
            onClick={cancelAnalysis}
            title="Stop the running analysis"
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-mono bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-all"
          >
            <Square size={12} />
            Cancel
          </button>
        ) : (
          <button
            onClick={startAnalysis}
            title="Run vulnerability analysis and patch generation"
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-mono bg-teal text-void font-semibold hover:bg-teal-bright transition-all shadow-[0_0_22px_rgba(30,144,176,0.25)]"
          >
            <Play size={12} />
            Analyze
          </button>
        )}
      </div>
    </div>
  );
}
