'use client';

import { useEffect, useState } from 'react';
import { useAnalysisStore } from '@/lib/store';
import {
  ShieldAlert,
  Brain,
  GitBranch,
  CheckCircle,
  AlertTriangle,
  Info,
  ChevronRight,
  Clipboard,
  RotateCcw,
  Check,
  Loader2,
  ArrowRight,
  BarChart3,
} from 'lucide-react';

/* ─── Vulnerabilities ────────────────────────────────────── */

function VulnerabilitiesTab() {
  const { vulnerabilities } = useAnalysisStore();

  if (vulnerabilities.length === 0) {
    return <EmptyState text="No vulnerabilities detected yet." />;
  }

  const severityColor: Record<string, string> = {
    CRITICAL: 'bg-red-500/10 text-red-400 border-red-500/20',
    HIGH:     'bg-orange-500/10 text-orange-400 border-orange-500/20',
    MEDIUM:   'bg-amber/10 text-amber border-amber/20',
    LOW:      'bg-teal/10 text-teal border-teal/20',
  };

  return (
    <div className="space-y-2">
      {vulnerabilities.map((v, i) => (
        <div key={i} className="group rounded-lg border border-border bg-surface/40 p-4 transition-colors hover:border-teal-dim/50">
          <div className="flex items-start justify-between gap-3 mb-2">
            <div className="flex items-center gap-2">
              <AlertTriangle size={13} className="text-amber shrink-0" />
              <span className="text-text-primary text-sm font-medium">{v.kind}</span>
            </div>
            <span className={`px-2 py-0.5 rounded border text-[10px] font-mono uppercase tracking-wider ${
              severityColor[v.severity?.toUpperCase()] || severityColor.MEDIUM
            }`}>
              {v.severity}
            </span>
          </div>
          <p className="text-text-muted text-xs leading-relaxed mb-2">{v.description}</p>
          <div className="flex items-center gap-2 text-text-ghost text-[10px] font-mono">
            <span>Node {v.node_id}</span>
            {v.location && (
              <>
                <span className="text-border">·</span>
                <span>{v.location}</span>
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ─── Reasoning ──────────────────────────────────────────── */

function ReasoningTab() {
  const { reasoning } = useAnalysisStore();

  if (reasoning.length === 0) {
    return <EmptyState text="Reasoning not available yet." />;
  }

  return (
    <div className="space-y-2">
      {reasoning.map((r, i) => (
        <div key={i} className="flex items-start gap-3 rounded-lg border border-border bg-surface/40 p-4">
          <ChevronRight size={13} className="text-teal-dim mt-0.5 shrink-0" />
          <p className="text-text-muted text-sm leading-relaxed">{r}</p>
        </div>
      ))}
    </div>
  );
}

/* ─── Patches ────────────────────────────────────────────── */

function PatchesTab() {
  const {
    patches,
    diff,
    changes,
    contextInfo,
    showPatched,
    patchedSource,
    applyPatchToEditor,
    undoPatchApply,
    canUndoPatchApply,
    isApplyingPatch,
    expirePatchUndo,
    patchActionMessage,
    clearPatchActionMessage,
  } = useAnalysisStore();
  const [copyDone, setCopyDone] = useState(false);
  const [undoSeconds, setUndoSeconds] = useState(0);

  useEffect(() => {
    if (!patchActionMessage) return;
    const timer = window.setTimeout(() => clearPatchActionMessage(), 3000);
    return () => window.clearTimeout(timer);
  }, [patchActionMessage, clearPatchActionMessage]);

  useEffect(() => {
    if (!copyDone) return;
    const timer = window.setTimeout(() => setCopyDone(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copyDone]);

  useEffect(() => {
    if (!canUndoPatchApply) {
      setUndoSeconds(0);
      return;
    }
    setUndoSeconds(8);
    const interval = window.setInterval(() => {
      setUndoSeconds((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    const expiry = window.setTimeout(() => expirePatchUndo(), 8000);
    return () => {
      window.clearInterval(interval);
      window.clearTimeout(expiry);
    };
  }, [canUndoPatchApply, expirePatchUndo]);

  if (patches.length === 0) {
    return <EmptyState text="No patches generated yet." />;
  }

  const copyPatch = async () => {
    const payload = diff?.trim() ? diff : patchedSource;
    if (!payload?.trim()) return;
    await navigator.clipboard.writeText(payload);
    setCopyDone(true);
  };

  const handleApplyPatch = async () => {
    await applyPatchToEditor();
  };

  return (
    <div className="space-y-4">
      {/* Toast */}
      {patchActionMessage && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-2.5 text-sm text-emerald-300 animate-in fade-in duration-200">
          <CheckCircle size={14} className="shrink-0" />
          <span>{patchActionMessage}</span>
        </div>
      )}

      {/* Action bar */}
      <div className="rounded-lg border border-border bg-surface/60 p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-medium text-text-primary mb-1">Apply the secure fix</h3>
            <p className="text-xs text-text-muted leading-relaxed">
              Replaces vulnerable source in the editor. Undo available for 8 seconds.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => void handleApplyPatch()}
              disabled={isApplyingPatch}
              className="inline-flex items-center gap-2 rounded-lg bg-teal px-4 py-2 text-sm font-medium text-void transition-all hover:bg-teal-bright disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isApplyingPatch ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <ArrowRight size={14} />
              )}
              {isApplyingPatch ? 'Applying' : 'Apply Patch'}
            </button>

            <button
              onClick={() => void copyPatch()}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-mono text-text-muted transition-all hover:border-teal-dim hover:text-text-primary"
            >
              {copyDone ? <Check size={12} className="text-emerald-400" /> : <Clipboard size={12} />}
              {copyDone ? 'Copied' : 'Copy Patch'}
            </button>
          </div>
        </div>

        {/* Undo bar */}
        {canUndoPatchApply && (
          <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-border bg-deep/60 px-3 py-2">
            <span className="text-xs text-text-muted">
              Undo available for <span className="font-mono text-text-primary">{undoSeconds}s</span>
            </span>
            <button
              onClick={undoPatchApply}
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs font-mono text-text-muted transition-all hover:border-teal-dim hover:text-text-primary"
            >
              <RotateCcw size={11} />
              Undo
            </button>
          </div>
        )}
      </div>

      {/* Diff */}
      {diff && (
        <div className="rounded-lg border border-border overflow-hidden" style={{ background: 'var(--color-surface)' }}>
          <div className="flex items-center justify-between px-4 py-2 border-b border-border">
            <span className="text-[10px] font-mono tracking-widest text-text-ghost uppercase">Unified Diff</span>
            {showPatched && (
              <span className="text-[10px] font-mono text-amber">Preview active</span>
            )}
          </div>
          <pre className="p-4 text-xs font-mono text-text-muted overflow-x-auto leading-relaxed">
            {diff.split('\n').map((line, i) => {
              let cls = '';
              if (line.startsWith('+') && !line.startsWith('+++')) cls = 'text-emerald-400';
              else if (line.startsWith('-') && !line.startsWith('---')) cls = 'text-red-400';
              else if (line.startsWith('@@')) cls = 'text-teal-dim';
              return <div key={i} className={cls}>{line}</div>;
            })}
          </pre>
        </div>
      )}

      {/* Changes */}
      {changes.length > 0 && (
        <div className="rounded-lg border border-border bg-surface/40 p-4">
          <h4 className="text-[10px] font-mono text-text-ghost uppercase tracking-widest mb-3">Changes</h4>
          <ul className="space-y-1.5">
            {changes.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-text-muted">
                <CheckCircle size={12} className="text-emerald-400 mt-0.5 shrink-0" />
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Context */}
      {contextInfo.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-mono text-text-ghost uppercase tracking-widest">Context</h4>
          {contextInfo.map((ctx, i) => (
            <div key={i} className="rounded-lg border border-border bg-surface/40 p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-amber">{ctx.cwe}</span>
                <span className="text-border">·</span>
                <span className="text-text-muted text-xs">{ctx.kind}</span>
              </div>
              {ctx.cpg_trace && (
                <div className="text-[10px] font-mono text-text-ghost">CPG: {ctx.cpg_trace}</div>
              )}
              {ctx.llm_rationale && (
                <p className="text-text-muted text-xs leading-relaxed">{ctx.llm_rationale}</p>
              )}
              {ctx.llm_strategy && (
                <div className="text-[10px] font-mono text-text-ghost">Strategy: {ctx.llm_strategy}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Verification ───────────────────────────────────────── */

function VerificationTab() {
  const { confidenceScore, confidenceBreakdown, sandbox, staticChecks } = useAnalysisStore();

  if (!confidenceBreakdown) {
    return <EmptyState text="Verification results pending." />;
  }

  const pct = (n: number) => `${Math.round(n * 100)}%`;
  const barColor = (n: number) => n >= 0.8 ? 'bg-emerald-400' : n >= 0.5 ? 'bg-amber' : 'bg-red-400';

  const breakdownItems = [
    { label: 'Static Safety',     value: confidenceBreakdown.static_safety ?? 1.0 },
    { label: 'Behavioral Match',  value: confidenceBreakdown.behavioural_match ?? 1.0 },
    { label: 'Patch Complexity',  value: confidenceBreakdown.patch_complexity ?? 1.0 },
    { label: 'CPG Coverage',      value: confidenceBreakdown.cpg_coverage ?? 1.0 },
  ];

  return (
    <div className="space-y-4">
      {/* Confidence */}
      <div className="rounded-lg border border-border bg-surface/40 p-5">
        <div className="flex items-center justify-between mb-4">
          <span className="text-[10px] font-mono text-text-ghost uppercase tracking-widest">Confidence Score</span>
          <BarChart3 size={13} className="text-text-ghost" />
        </div>
        <div className="text-4xl font-display font-light text-text-primary mb-3 text-center tracking-tight">
          {pct(confidenceScore)}
        </div>
        <div className="h-1.5 rounded-full bg-border overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${barColor(confidenceScore)}`}
            style={{ width: pct(confidenceScore) }}
          />
        </div>
      </div>

      {/* Breakdown */}
      <div className="rounded-lg border border-border bg-surface/40 p-4 space-y-3">
        <h4 className="text-[10px] font-mono text-text-ghost uppercase tracking-widest mb-1">Breakdown</h4>
        {breakdownItems.map(item => (
          <div key={item.label}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-text-muted text-xs">{item.label}</span>
              <span className="text-text-primary text-xs font-mono">{pct(item.value)}</span>
            </div>
            <div className="h-1 rounded-full bg-border overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${barColor(item.value)}`}
                style={{ width: pct(item.value) }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Sandbox */}
      {sandbox && (
        <div className="rounded-lg border border-border bg-surface/40 p-4">
          <h4 className="text-[10px] font-mono text-text-ghost uppercase tracking-widest mb-3">Sandbox Verification</h4>
          <div className="grid grid-cols-2 gap-2">
            <StatusBadge label="Original Runs" ok={sandbox.original_runs} />
            <StatusBadge label="Patched Runs" ok={sandbox.patched_runs} />
            <StatusBadge label="Behavior Match" ok={sandbox.behaviour_match} />
            <StatusBadge label="Tests Passed" ok={sandbox.test_passed} />
          </div>
          {sandbox.test_count > 0 && (
            <div className="mt-3 text-text-ghost text-[10px] font-mono">
              {sandbox.test_pass_count}/{sandbox.test_count} tests passed
            </div>
          )}
        </div>
      )}

      {/* Static checks */}
      {staticChecks.length > 0 && (
        <div className="rounded-lg border border-border bg-surface/40 p-4">
          <h4 className="text-[10px] font-mono text-text-ghost uppercase tracking-widest mb-3">Static Checks</h4>
          <div className="space-y-1.5">
            {staticChecks.map((check, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                {check.passed
                  ? <CheckCircle size={12} className="text-emerald-400 mt-0.5 shrink-0" />
                  : <AlertTriangle size={12} className="text-red-400 mt-0.5 shrink-0" />}
                <span className="text-text-muted">{check.details}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Shared ─────────────────────────────────────────────── */

function StatusBadge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-md border text-xs ${
      ok ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-400'
         : 'border-red-500/20 bg-red-500/5 text-red-400'
    }`}>
      {ok ? <CheckCircle size={11} /> : <AlertTriangle size={11} />}
      {label}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-8 h-8 rounded-full border border-border flex items-center justify-center mb-3">
        <Info size={14} className="text-text-ghost" />
      </div>
      <p className="text-text-ghost text-sm">{text}</p>
    </div>
  );
}

/* ─── Tab config ─────────────────────────────────────────── */

const TABS = [
  { key: 'vulnerabilities' as const, label: 'Vulnerabilities', Icon: ShieldAlert },
  { key: 'reasoning' as const,       label: 'Reasoning',       Icon: Brain },
  { key: 'patches' as const,         label: 'Patches',         Icon: GitBranch },
  { key: 'verification' as const,    label: 'Verification',    Icon: CheckCircle },
];

/* ─── Main Panel ─────────────────────────────────────────── */

export function ResultsPanel() {
  const { activeTab, setActiveTab, vulnerabilities, stage } = useAnalysisStore();
  const vulnCount = vulnerabilities.length;

  return (
    <div className="flex flex-col h-full rounded-xl border border-border overflow-hidden" style={{ background: 'var(--color-deep)' }}>
      {/* Tab bar */}
      <div className="flex border-b border-border px-1 overflow-x-auto" style={{ background: 'var(--color-surface)' }}>
        {TABS.map(tab => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-mono tracking-wide transition-colors whitespace-nowrap border-b-2 ${
                isActive
                  ? 'text-text-primary border-teal'
                  : 'text-text-ghost border-transparent hover:text-text-muted'
              }`}
            >
              <tab.Icon size={12} />
              {tab.label}
              {tab.key === 'vulnerabilities' && vulnCount > 0 && (
                <span className="ml-1 px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 text-[9px] font-mono">
                  {vulnCount}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {stage === 'idle' && <EmptyState text="Submit code to begin analysis." />}
        {stage !== 'idle' && activeTab === 'vulnerabilities' && <VulnerabilitiesTab />}
        {stage !== 'idle' && activeTab === 'reasoning' && <ReasoningTab />}
        {stage !== 'idle' && activeTab === 'patches' && <PatchesTab />}
        {stage !== 'idle' && activeTab === 'verification' && <VerificationTab />}
      </div>
    </div>
  );
}
