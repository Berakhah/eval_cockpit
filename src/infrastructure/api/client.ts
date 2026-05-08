/**
 * Typed HTTP client for the PolyEval API.
 * Runs server-side in TanStack Start server functions.
 */
import type { Submission, SubmissionInput, SubmissionListItem } from "@/domain/submission";
import { ApiError, NetworkError } from "./errors";
import { signRequest } from "./sign";

const API_BASE =
  (typeof process !== "undefined" && process.env.POLYEVAL_API_URL) ||
  "http://localhost:8000";

const TENANT =
  (typeof process !== "undefined" && process.env.POLYEVAL_TENANT_ID) ||
  "demo";

const HMAC_SECRET =
  (typeof process !== "undefined" && process.env.POLYEVAL_HMAC_SECRET) || "";

async function apiFetch<T>(
  path: string,
  options: RequestInit & { bodyStr?: string } = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const bodyStr = options.bodyStr ?? "";
  const bodyBytes = bodyStr ? new TextEncoder().encode(bodyStr) : new Uint8Array(0);
  const authHeaders = await signRequest(bodyBytes, TENANT, HMAC_SECRET);

  const headers: Record<string, string> = {
    ...authHeaders,
    "Content-Type": "application/json",
  };

  let resp: Response;
  try {
    resp = await fetch(url, {
      ...options,
      body: bodyStr || undefined,
      headers,
    });
  } catch (err) {
    throw new NetworkError(err, url);
  }

  if (!resp.ok) {
    const detail = await resp.text().catch(() => resp.statusText);
    throw new ApiError(resp.status, detail, url);
  }

  return resp.json() as Promise<T>;
}

interface SubmitResponse {
  id: string;
  replay: boolean;
}

export async function submitEvaluation(
  input: SubmissionInput,
): Promise<SubmitResponse> {
  const body = JSON.stringify({
    model_id: input.modelId,
    language: input.language,
    prompt: input.prompt ?? "",
    code: input.code,
    test_suite: {
      framework: input.testSuite.framework,
      files: input.testSuite.files,
      entrypoint: input.testSuite.entrypoint,
    },
    trials: input.trials,
    timeout_seconds: input.timeoutSeconds,
    memory_limit_mb: input.memoryLimitMb,
  });
  return apiFetch<SubmitResponse>("/v1/submissions", {
    method: "POST",
    bodyStr: body,
  });
}

export async function getEvaluation(id: string): Promise<Submission | null> {
  try {
    const raw = await apiFetch<Record<string, unknown>>(`/v1/submissions/${id}`);
    return mapSubmission(raw);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function listEvaluations(): Promise<SubmissionListItem[]> {
  const rows = await apiFetch<Record<string, unknown>[]>("/v1/submissions");
  return rows.map(mapListItem);
}

// ─── Response mappers ─────────────────────────────────────────────────────────

function mapSubmission(raw: Record<string, unknown>): Submission {
  return {
    id: String(raw.id),
    tenantId: String(raw.tenant_id),
    modelId: String(raw.model_id),
    language: raw.language as Submission["language"],
    status: raw.status as Submission["status"],
    version: Number(raw.version),
    createdAt: String(raw.created_at),
    updatedAt: String(raw.updated_at),
    replay: Boolean((raw as { replay?: boolean }).replay),
    result: raw.result ? mapResult(raw.result as Record<string, unknown>) : null,
  };
}

function mapResult(r: Record<string, unknown>) {
  const ci = (v: unknown): { lo: number; hi: number } => {
    const obj = v as { lo: number; hi: number } | null;
    return obj ?? { lo: 0, hi: 0 };
  };
  return {
    correctness: Number(r.correctness),
    correctness_ci: ci(r.correctness_ci),
    reliability: Number(r.reliability),
    flaky: Boolean(r.flaky),
    perf_normalized: r.perf_normalized != null ? Number(r.perf_normalized) : null,
    perf_ci: r.perf_ci ? ci(r.perf_ci) : null,
    trials_total: Number(r.trials_total),
    trials_passed: Number(r.trials_passed),
    wall_time_ms_p50: Number(r.wall_time_ms_p50),
    wall_time_ms_p95: Number(r.wall_time_ms_p95),
    mem_peak_mb: r.mem_peak_mb != null ? Number(r.mem_peak_mb) : null,
    attestation_pubkey_id: String(r.attestation_pubkey_id),
    scored_at: String(r.scored_at),
    raw_trials: Array.isArray(r.raw_trials) ? r.raw_trials : [],
  };
}

function mapListItem(raw: Record<string, unknown>): SubmissionListItem {
  return {
    id: String(raw.id),
    tenantId: String(raw.tenant_id),
    modelId: String(raw.model_id),
    language: raw.language as SubmissionListItem["language"],
    status: raw.status as SubmissionListItem["status"],
    trialsTotal: raw.trials_total != null ? Number(raw.trials_total) : null,
    correctness: raw.correctness != null ? Number(raw.correctness) : null,
    perfNormalized: raw.perf_normalized != null ? Number(raw.perf_normalized) : null,
    reliability: raw.reliability != null ? Number(raw.reliability) : null,
    createdAt: String(raw.created_at),
  };
}
