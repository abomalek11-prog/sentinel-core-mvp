'use client';

import { useEffect, useRef, useState } from 'react';
import { useAnalysisStore } from '@/lib/store';

let monacoPromise: Promise<typeof import('monaco-editor')> | null = null;
function loadMonaco() {
  if (!monacoPromise) {
    monacoPromise = import('monaco-editor').catch(() => null) as Promise<typeof import('monaco-editor')>;
  }
  return monacoPromise;
}

export function EditorPanel() {
  const {
    sourceCode,
    setSourceCode,
    fileName,
    setFileName,
    showPatched,
    patchedSource,
    stage,
    editorPatchedFlash,
  } = useAnalysisStore();
  const editorContainerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<import('monaco-editor').editor.IStandaloneCodeEditor | null>(null);
  const [loaded, setLoaded] = useState(false);
  const isRunning = !['idle', 'done', 'error'].includes(stage);

  const displayCode = showPatched && patchedSource ? patchedSource : sourceCode;

  useEffect(() => {
    let disposed = false;

    (async () => {
      const monaco = await loadMonaco();
      if (disposed || !monaco || !editorContainerRef.current) return;

      // Define Netra theme
      monaco.editor.defineTheme('netra', {
        base: 'vs-dark',
        inherit: true,
        rules: [
          { token: 'comment', foreground: '3A6A82', fontStyle: 'italic' },
          { token: 'keyword', foreground: '2CA5C8' },
          { token: 'string', foreground: 'FFC44D' },
          { token: 'number', foreground: 'FFC44D' },
          { token: 'type', foreground: '1E90B0' },
          { token: 'function', foreground: 'D6E8F0' },
        ],
        colors: {
          'editor.background': '#080F18',
          'editor.foreground': '#D6E8F0',
          'editorCursor.foreground': '#1E90B0',
          'editor.lineHighlightBackground': '#0C182820',
          'editor.selectionBackground': '#1E90B030',
          'editorLineNumber.foreground': '#1E3A4A',
          'editorLineNumber.activeForeground': '#3A6A82',
          'editor.inactiveSelectionBackground': '#1E90B015',
          'editorIndentGuide.background': '#0D203350',
          'editorWidget.background': '#0C1828',
          'editorWidget.border': '#0D2033',
        },
      });

      const editor = monaco.editor.create(editorContainerRef.current, {
        value: displayCode,
        language: 'python',
        theme: 'netra',
        fontSize: 13,
        fontFamily: "'JetBrains Mono', monospace",
        lineHeight: 22,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        padding: { top: 16, bottom: 16 },
        wordWrap: 'on',
        automaticLayout: true,
        renderLineHighlight: 'line',
        smoothScrolling: true,
        cursorBlinking: 'smooth',
        cursorSmoothCaretAnimation: 'on',
        readOnly: showPatched,
      });

      editor.onDidChangeModelContent(() => {
        if (!showPatched) {
          setSourceCode(editor.getValue());
        }
      });

      editorRef.current = editor;
      setLoaded(true);
    })();

    return () => {
      disposed = true;
      editorRef.current?.dispose();
      editorRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync value when showPatched or patchedSource changes
  useEffect(() => {
    if (editorRef.current) {
      const model = editorRef.current.getModel();
      if (model && model.getValue() !== displayCode) {
        console.log('[EditorPanel] syncing editor content', {
          oldLen: model.getValue().length,
          newLen: displayCode.length,
          showPatched,
        });
        model.setValue(displayCode);
      }
      editorRef.current.updateOptions({ readOnly: showPatched });
    }
  }, [displayCode, showPatched]);

  return (
    <div
      className={`relative flex flex-col h-full rounded-xl border overflow-hidden transition-all duration-500 ${
        editorPatchedFlash
          ? 'border-emerald-400/50 ring-1 ring-emerald-400/25'
          : 'border-border'
      }`}
      style={{ background: 'var(--color-deep)' }}
    >
      {/* Editor chrome */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border" style={{ background: 'var(--color-surface)' }}>
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/60" />
            <div className="w-3 h-3 rounded-full bg-amber/60" />
            <div className="w-3 h-3 rounded-full bg-emerald-500/60" />
          </div>
          <input
            value={fileName}
            onChange={(e) => setFileName(e.target.value)}
            className="bg-transparent text-text-muted text-xs font-mono border-none outline-none w-32"
            spellCheck={false}
          />
        </div>
        <div className="flex items-center gap-2">
          {isRunning && (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-teal/20 bg-teal/10 text-[10px] font-mono uppercase tracking-widest text-teal animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-teal" />
              analyzing
            </span>
          )}
          {showPatched && (
            <span className="text-[10px] font-mono tracking-widest text-amber uppercase">Patched</span>
          )}
        </div>
      </div>

      {/* Monaco */}
      <div ref={editorContainerRef} className="flex-1 min-h-0" />

      {editorPatchedFlash && (
        <div className="pointer-events-none absolute inset-0 bg-emerald-400/5 animate-pulse" />
      )}

      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-deep/80 backdrop-blur-sm">
          <span className="text-text-ghost text-sm font-mono animate-pulse">Loading editor…</span>
        </div>
      )}
    </div>
  );
}
