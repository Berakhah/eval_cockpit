export type Language = "python" | "javascript" | "java" | "cpp" | "rust";

export const LANGUAGES: readonly Language[] = [
  "python",
  "javascript",
  "java",
  "cpp",
  "rust",
] as const;

export type Status = "queued" | "running" | "scored" | "failed";

export const LANGUAGE_FRAMEWORK: Record<Language, string> = {
  python: "pytest",
  javascript: "jest",
  java: "junit",
  cpp: "gtest",
  rust: "cargo_test",
} as const;

export interface TestFile {
  name: string;
  content: string;
}

export interface TestSuite {
  framework: string;
  files: TestFile[];
  entrypoint: string;
}

export interface SubmissionInput {
  modelId: string;
  language: Language;
  prompt: string;
  code: string;
  testSuite: TestSuite;
  trials: number;
  timeoutSeconds: number;
  memoryLimitMb: number;
}

export interface SubmissionMeta {
  id: string;
  tenantId: string;
  modelId: string;
  language: Language;
  status: Status;
  version: number;
  createdAt: string; // ISO string from API
  updatedAt: string;
  replay: boolean;
}

export interface CI {
  lo: number;
  hi: number;
}

export interface Trial {
  index: number;
  wall_ns: number;
  mem_kb: number;
  exit_code: number;
  framework_passed: boolean;
  sandbox_violation: boolean;
  stderr_snippet: string | null;
}

export interface ScoredResult {
  correctness: number;
  correctness_ci: CI;
  reliability: number;
  flaky: boolean;
  perf_normalized: number | null;
  perf_ci: CI | null;
  trials_total: number;
  trials_passed: number;
  wall_time_ms_p50: number;
  wall_time_ms_p95: number;
  mem_peak_mb: number | null;
  attestation_pubkey_id: string;
  scored_at: string;
  raw_trials: Trial[];
}

export interface Submission extends SubmissionMeta {
  result: ScoredResult | null;
}

export interface SubmissionListItem {
  id: string;
  tenantId: string;
  modelId: string;
  language: Language;
  status: Status;
  trialsTotal: number | null;
  correctness: number | null;
  perfNormalized: number | null;
  reliability: number | null;
  createdAt: string;
}

export const isTerminal = (s: Status): boolean => s === "scored" || s === "failed";
