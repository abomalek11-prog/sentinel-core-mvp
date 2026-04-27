import { create } from 'zustand';
import type {
  Vulnerability,
  PatchSuggestion,
  ContextInfo,
  ConfidenceBreakdown,
  SandboxVerification,
  StaticCheck,
  PipelineStage,
  SSEEventType,
  SSEStatusData,
  SSEVulnData,
  SSEReasoningData,
  SSEPatchData,
  SSEVerificationData,
  SSEDoneData,
  SSEErrorData,
} from '@/types/sentinel';
import { fetchDemo, streamAnalysis } from '@/lib/api';

interface AnalysisStore {
  /* ── Source ─────────────────────────────────── */
  sourceCode: string;
  fileName: string;
  setSourceCode: (code: string) => void;
  setFileName: (name: string) => void;

  /* ── Pipeline state ─────────────────────────── */
  stage: PipelineStage;
  statusMessage: string;
  analysisId: string | null;
  cpgNodes: number;
  cpgEdges: number;

  /* ── Results ────────────────────────────────── */
  vulnerabilities: Vulnerability[];
  reasoning: string[];
  patches: PatchSuggestion[];
  patchedSource: string;
  diff: string;
  changes: string[];
  contextInfo: ContextInfo[];
  confidenceScore: number;
  confidenceBreakdown: ConfidenceBreakdown | null;
  sandbox: SandboxVerification | null;
  staticChecks: StaticCheck[];
  llmModel: string;
  error: string | null;

  /* ── UI state ───────────────────────────────── */
  activeTab: 'vulnerabilities' | 'reasoning' | 'patches' | 'verification';
  showPatched: boolean;
  patchActionMessage: string;
  canUndoPatchApply: boolean;
  isApplyingPatch: boolean;
  editorPatchedFlash: boolean;
  setActiveTab: (tab: AnalysisStore['activeTab']) => void;
  setShowPatched: (show: boolean) => void;
  applyPatchToEditor: () => Promise<boolean>;
  undoPatchApply: () => boolean;
  expirePatchUndo: () => void;
  clearPatchActionMessage: () => void;

  /* ── Actions ────────────────────────────────── */
  startAnalysis: () => void;
  loadDemoAndRun: () => Promise<void>;
  cancelAnalysis: () => void;
  reset: () => void;

  /* ── Internal ───────────────────────────────── */
  _controller: AbortController | null;
  _preApplySource: string;
}

const initialResults = {
  stage: 'idle' as PipelineStage,
  statusMessage: '',
  analysisId: null as string | null,
  cpgNodes: 0,
  cpgEdges: 0,
  vulnerabilities: [] as Vulnerability[],
  reasoning: [] as string[],
  patches: [] as PatchSuggestion[],
  patchedSource: '',
  diff: '',
  changes: [] as string[],
  contextInfo: [] as ContextInfo[],
  confidenceScore: 0,
  confidenceBreakdown: null as ConfidenceBreakdown | null,
  sandbox: null as SandboxVerification | null,
  staticChecks: [] as StaticCheck[],
  llmModel: '',
  error: null as string | null,
};

export const useAnalysisStore = create<AnalysisStore>((set, get) => ({
  sourceCode: '',
  fileName: 'untitled.py',
  ...initialResults,
  activeTab: 'vulnerabilities',
  showPatched: false,
  patchActionMessage: '',
  canUndoPatchApply: false,
  isApplyingPatch: false,
  editorPatchedFlash: false,
  _controller: null,
  _preApplySource: '',

  setSourceCode: (code) => set({ sourceCode: code }),
  setFileName: (name) => set({ fileName: name }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setShowPatched: (show) => set({ showPatched: show }),
  clearPatchActionMessage: () => set({ patchActionMessage: '' }),

  applyPatchToEditor: async () => {
    const { patchedSource, sourceCode, isApplyingPatch } = get();
    console.log('[ApplyPatch] triggered', {
      hasPatchedSource: !!patchedSource.trim(),
      patchedLen: patchedSource.length,
      sourceLen: sourceCode.length,
      identical: patchedSource === sourceCode,
    });
    if (isApplyingPatch) {
      console.log('[ApplyPatch] skipped — already applying');
      return false;
    }
    if (!patchedSource.trim()) {
      console.warn('[ApplyPatch] no patch available');
      set({ patchActionMessage: 'No patch available to apply.' });
      return false;
    }
    if (patchedSource === sourceCode) {
      console.warn('[ApplyPatch] patched source identical to current source');
      set({ patchActionMessage: 'No effective patch changes to apply.' });
      return false;
    }

    set({ isApplyingPatch: true });
    await new Promise((resolve) => window.setTimeout(resolve, 420));

    console.log('[ApplyPatch] replacing editor content', {
      oldLen: sourceCode.length,
      newLen: patchedSource.length,
    });

    set({
      _preApplySource: sourceCode,
      sourceCode: patchedSource,
      showPatched: false,
      patchActionMessage: 'Patch applied successfully',
      canUndoPatchApply: true,
      editorPatchedFlash: true,
      isApplyingPatch: false,
      activeTab: 'patches',
    });

    console.log('[ApplyPatch] success — editor updated, undo available for 8s');

    window.setTimeout(() => {
      set({ editorPatchedFlash: false });
    }, 900);

    return true;
  },

  undoPatchApply: () => {
    const { _preApplySource, canUndoPatchApply } = get();
    console.log('[UndoPatch] triggered', { canUndo: canUndoPatchApply });
    if (!canUndoPatchApply) {
      return false;
    }

    console.log('[UndoPatch] reverting editor to pre-apply source');
    set({
      sourceCode: _preApplySource,
      showPatched: false,
      patchActionMessage: 'Patch reverted',
      canUndoPatchApply: false,
      editorPatchedFlash: false,
      _preApplySource: '',
      activeTab: 'patches',
    });
    return true;
  },

  expirePatchUndo: () => {
    set({ canUndoPatchApply: false, _preApplySource: '' });
  },

  reset: () => {
    const ctrl = get()._controller;
    if (ctrl) ctrl.abort();
    set({
      ...initialResults,
      _controller: null,
      activeTab: 'vulnerabilities',
      showPatched: false,
      patchActionMessage: '',
      canUndoPatchApply: false,
      isApplyingPatch: false,
      editorPatchedFlash: false,
      _preApplySource: '',
    });
  },

  cancelAnalysis: () => {
    const ctrl = get()._controller;
    if (ctrl) ctrl.abort();
    set({ stage: 'idle', _controller: null, statusMessage: 'Analysis cancelled' });
  },

  loadDemoAndRun: async () => {
    try {
      const demo = await fetchDemo();
      set({ sourceCode: demo.source_code, fileName: demo.file_name });
      // Small delay so the editor picks up the new source before analysis starts
      await new Promise((r) => setTimeout(r, 300));
      get().startAnalysis();
    } catch (err) {
      console.error('[Demo] failed to load demo', err);
      set({ stage: 'error', error: 'Failed to load demo code', statusMessage: 'Demo failed' });
    }
  },

  startAnalysis: () => {
    const { sourceCode, fileName, _controller } = get();
    if (_controller) _controller.abort();
    if (!sourceCode.trim()) return;

    set({
      ...initialResults,
      stage: 'parsing',
      statusMessage: 'Initializing…',
      patchActionMessage: '',
      canUndoPatchApply: false,
      isApplyingPatch: false,
      editorPatchedFlash: false,
      _preApplySource: '',
    });

    const mapStage = (s: string): PipelineStage => {
      if (s.includes('pars'))   return 'parsing';
      if (s.includes('CPG') || s.includes('cpg') || s.includes('graph')) return 'building_cpg';
      if (s.includes('detect') || s.includes('vuln')) return 'detecting';
      if (s.includes('reason') || s.includes('analy')) return 'reasoning';
      if (s.includes('patch'))  return 'patching';
      if (s.includes('verif') || s.includes('sandbox')) return 'verifying';
      return 'parsing';
    };

    const handleEvent = (event: SSEEventType, data: unknown) => {
      switch (event) {
        case 'status': {
          const d = data as SSEStatusData;
          set({
            statusMessage: d.stage,
            stage: mapStage(d.stage),
            ...(d.analysis_id ? { analysisId: d.analysis_id } : {}),
            ...(d.cpg_nodes != null ? { cpgNodes: d.cpg_nodes } : {}),
            ...(d.cpg_edges != null ? { cpgEdges: d.cpg_edges } : {}),
          });
          break;
        }
        case 'vulnerabilities': {
          const d = data as SSEVulnData;
          set({ vulnerabilities: d.vulnerabilities, stage: 'detecting' });
          break;
        }
        case 'reasoning': {
          const d = data as SSEReasoningData;
          set({ reasoning: d.reasoning, stage: 'reasoning' });
          break;
        }
        case 'patch': {
          const d = data as SSEPatchData;
          const currentSource = get().sourceCode;
          console.log('[SSE:patch] received', {
            patchedSourceLen: d.patched_source?.length ?? 0,
            currentSourceLen: currentSource.length,
            sourcesIdentical: d.patched_source === currentSource,
            hasDiff: !!d.diff,
            patchCount: d.patches?.length ?? 0,
            patchedSourcePreview: d.patched_source?.slice(0, 200),
          });
          set({
            patches: d.patches,
            patchedSource: d.patched_source,
            diff: d.diff,
            changes: d.changes,
            contextInfo: d.context_info,
            stage: 'patching',
          });
          break;
        }
        case 'verification': {
          const d = data as SSEVerificationData;
          set({
            confidenceScore: d.confidence_score,
            confidenceBreakdown: d.confidence_breakdown,
            sandbox: d.sandbox,
            staticChecks: d.static_checks,
            stage: 'verifying',
          });
          break;
        }
        case 'done': {
          const d = data as SSEDoneData;
          set({
            stage: 'done',
            llmModel: d.llm_model,
            statusMessage: 'Analysis complete',
            activeTab: 'vulnerabilities',
          });
          break;
        }
        case 'error': {
          const d = data as SSEErrorData;
          set({ stage: 'error', error: d.error, statusMessage: 'Analysis failed' });
          break;
        }
      }
    };

    const ctrl = streamAnalysis(
      { source_code: sourceCode, file_name: fileName },
      handleEvent,
      (err) => set({ stage: 'error', error: err.message, statusMessage: 'Connection failed' }),
    );

    set({ _controller: ctrl });
  },
}));
