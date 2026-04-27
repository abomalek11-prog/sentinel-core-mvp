/* ═══════════════════════════════════════════════════════════
   Netra — TypeScript types mirroring the backend API schemas
   ═══════════════════════════════════════════════════════════ */

export interface AnalyzeRequest {
  source_code: string;
  file_name?: string;
  language?: 'python';
}

export interface Vulnerability {
  node_id: string;
  kind: string;
  severity: string;
  description: string;
  location: string;
}

export interface PatchSuggestion {
  original: string;
  patched: string;
  description: string;
  target_location: string;
}

export interface ContextInfo {
  kind: string;
  cwe: string;
  location: string;
  function: string;
  source_text: string;
  cpg_trace: string;
  fix: string;
  llm_strategy: string;
  llm_rationale: string;
  llm_test_hint: string;
}

export interface PatchReport {
  patched_source: string;
  diff: string;
  changes: string[];
  imports_added: string[];
  context_info: ContextInfo[];
  patch_complexity: number;
}

export interface SandboxVerification {
  original_runs: boolean;
  patched_runs: boolean;
  behaviour_match: boolean;
  test_passed: boolean;
  test_output: string;
  details: string;
  test_count: number;
  test_pass_count: number;
}

export interface ConfidenceBreakdown {
  static_safety: number;
  behavioural_match: number;
  patch_complexity: number;
  cpg_coverage: number;
  overall: number;
}

export interface StaticCheck {
  passed: boolean;
  details: string;
}

export interface Verification {
  static_checks: StaticCheck[];
  sandbox: SandboxVerification;
  confidence_score: number;
  confidence_breakdown: ConfidenceBreakdown;
}

export interface AnalysisResponse {
  analysis_id: string;
  status: string;
  file_name: string;
  language: string;
  llm_model: string;
  source_code: string;
  vulnerabilities: Vulnerability[];
  reasoning: string[];
  patches: PatchSuggestion[];
  patch_report: PatchReport | null;
  verification: Verification | null;
  error?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  llm_ready: boolean;
  llm_model: string;
}

export interface DemoResponse {
  source_code: string;
  file_name: string;
  description: string;
}

/* ── SSE Event Types ──────────────────────────────────────── */

export type SSEEventType =
  | 'status'
  | 'vulnerabilities'
  | 'reasoning'
  | 'patch'
  | 'verification'
  | 'done'
  | 'error';

export interface SSEStatusData {
  stage: string;
  analysis_id?: string;
  cpg_nodes?: number;
  cpg_edges?: number;
}

export interface SSEVulnData {
  vulnerabilities: Vulnerability[];
  count: number;
}

export interface SSEReasoningData {
  reasoning: string[];
}

export interface SSEPatchData {
  patches: PatchSuggestion[];
  diff: string;
  changes: string[];
  patched_source: string;
  context_info: ContextInfo[];
}

export interface SSEVerificationData {
  confidence_score: number;
  confidence_breakdown: ConfidenceBreakdown;
  sandbox: SandboxVerification;
  static_checks: StaticCheck[];
}

export interface SSEDoneData {
  analysis_id: string;
  vuln_count: number;
  patch_count: number;
  confidence: number;
  llm_model: string;
}

export interface SSEErrorData {
  error: string;
  analysis_id: string;
}

/* ── Pipeline Stage ───────────────────────────────────────── */

export type PipelineStage =
  | 'idle'
  | 'parsing'
  | 'building_cpg'
  | 'detecting'
  | 'reasoning'
  | 'patching'
  | 'verifying'
  | 'done'
  | 'error';
