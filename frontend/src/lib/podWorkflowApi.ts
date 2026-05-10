import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";

export type PodExtractResponse = {
  run_id: string;
  status: string;
  overall_confidence: number;
  extracted: any;
};

async function authHeader(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error("Not authenticated");
  return { Authorization: `Bearer ${session.access_token}` };
}

export async function extractPod(
  podId: string,
  file: File,
  extractionHint?: string
): Promise<PodExtractResponse> {
  const headers = await authHeader();
  const formData = new FormData();
  formData.append("file", file);

  const url =
    extractionHint
      ? apiUrl(`/api/pods/${encodeURIComponent(podId)}/extract?extraction_hint=${encodeURIComponent(extractionHint)}`)
      : apiUrl(`/api/pods/${encodeURIComponent(podId)}/extract`);

  const resp = await fetch(url, { method: "POST", headers, body: formData });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `Extract failed (${resp.status})`);
  }
  return await resp.json();
}

export async function listUserPodRuns(
  podId: string,
  page = 1,
  limit = 20,
  status?: string
): Promise<{ runs: any[]; page: number; limit: number }> {
  const headers = await authHeader();
  let url = apiUrl(`/api/pods/${encodeURIComponent(podId)}/runs?page=${page}&limit=${limit}`);
  if (status) url += `&status=${encodeURIComponent(status)}`;
  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error(await resp.text() || `List runs failed (${resp.status})`);
  return await resp.json();
}

export async function getPodRun(
  podId: string,
  runId: string
): Promise<{ run: any }> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/runs/${encodeURIComponent(runId)}`), { headers });
  if (!resp.ok) throw new Error(await resp.text() || `Get run failed (${resp.status})`);
  return await resp.json();
}

export async function getPodRunHealthCard(
  podId: string,
  runId: string
): Promise<{
  run: any;
  confidence_evaluation: any;
  latest_training_job: any;
  latest_eval_results: any[];
  quality_gate_snapshot: any;
}> {
  const headers = await authHeader();
  const resp = await fetch(
    apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/runs/${encodeURIComponent(runId)}/health-card`),
    { headers }
  );
  if (!resp.ok) throw new Error(await resp.text() || `Health card failed (${resp.status})`);
  return await resp.json();
}

export async function submitPodRun(
  podId: string,
  runId: string,
  body: {
    thumbs_up: boolean;
    notes?: string;
    corrected_json?: any;
    require_admin_approval_for_training?: boolean;
  }
): Promise<{ status: string }> {
  const headers = { ...(await authHeader()), "Content-Type": "application/json" };
  const resp = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/runs/${encodeURIComponent(runId)}/submit`), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(await resp.text() || `Submit failed (${resp.status})`);
  return await resp.json();
}

export async function reExtractPodRun(
  podId: string,
  runId: string,
  extractionHint?: string,
  file?: File
): Promise<PodExtractResponse> {
  const headers = await authHeader();

  const formData = new FormData();
  formData.append("body", JSON.stringify({ extraction_hint: extractionHint ?? null }));
  if (file) formData.append("file", file);

  const resp = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/runs/${encodeURIComponent(runId)}/re-extract`), {
    method: "POST",
    headers,
    body: formData,
  });

  if (!resp.ok) throw new Error(await resp.text() || `Re-extract failed (${resp.status})`);
  return await resp.json();
}

export async function adminQueueStats(podId: string): Promise<Record<string, number>> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/queue/stats`), { headers });
  if (!resp.ok) throw new Error(await resp.text() || `Stats failed (${resp.status})`);
  return await resp.json();
}

export type PodAdminQueueFilters = {
  states?: string;
  conf_min?: number;
  conf_max?: number;
  order_by?: "priority" | "created_at" | "updated_at";
  order_dir?: "asc" | "desc";
  page?: number;
  limit?: number;
};

export async function listPodAdminQueue(
  podId: string,
  filters: PodAdminQueueFilters = {}
): Promise<{ queue: any[]; page: number; limit: number }> {
  const headers = await authHeader();
  const params = new URLSearchParams();
  if (filters.states) params.set("states", filters.states);
  if (filters.conf_min != null) params.set("conf_min", String(filters.conf_min));
  if (filters.conf_max != null) params.set("conf_max", String(filters.conf_max));
  if (filters.order_by) params.set("order_by", filters.order_by);
  if (filters.order_dir) params.set("order_dir", filters.order_dir);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.limit) params.set("limit", String(filters.limit));

  const qs = params.toString();
  const resp = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/queue${qs ? `?${qs}` : ""}`), { headers });
  if (!resp.ok) throw new Error(await resp.text() || `Queue failed (${resp.status})`);
  const data = await resp.json();
  return { queue: data.queue || [], page: data.page ?? 1, limit: data.limit ?? 25 };
}

export async function batchReviewPodRuns(
  podId: string,
  runIds: string[],
  decision: "approve" | "reject",
  notes?: string
): Promise<{ decision: string; succeeded: number; total: number; results: any[] }> {
  const headers = { ...(await authHeader()), "Content-Type": "application/json" };
  const resp = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/batch-review`), {
    method: "POST",
    headers,
    body: JSON.stringify({ run_ids: runIds, decision, notes }),
  });
  if (!resp.ok) throw new Error(await resp.text() || `Batch review failed (${resp.status})`);
  return await resp.json();
}

export async function adminReviewPodRun(
  podId: string,
  runId: string,
  body: { decision: "approve" | "rework" | "reject"; notes?: string; corrected_json?: any }
): Promise<{ status: string }> {
  const headers = { ...(await authHeader()), "Content-Type": "application/json" };
  const resp = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/${encodeURIComponent(runId)}/review`), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(await resp.text() || `Admin review failed (${resp.status})`);
  return await resp.json();
}

export async function patchPodQueueItem(
  podId: string,
  runId: string,
  patch: { priority?: number; assigned_to?: string; state?: string }
): Promise<{ updated: Record<string, any> }> {
  const headers = { ...(await authHeader()), "Content-Type": "application/json" };
  const resp = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/queue/${encodeURIComponent(runId)}/detail`), {
    method: "PATCH",
    headers,
    body: JSON.stringify(patch),
  });
  if (!resp.ok) throw new Error(await resp.text() || `Patch failed (${resp.status})`);
  return await resp.json();
}

export async function listTrainingJobs(
  podId: string,
  page = 1,
  limit = 20,
  status?: string
): Promise<{ jobs: any[]; page: number; limit: number }> {
  const headers = await authHeader();
  let url = apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/jobs?page=${page}&limit=${limit}`);
  if (status) url += `&status=${encodeURIComponent(status)}`;
  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error(await resp.text() || `Jobs failed (${resp.status})`);
  return await resp.json();
}

export async function getJobByRunId(
  podId: string,
  runId: string
): Promise<{ job: any | null }> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/jobs/by-run/${encodeURIComponent(runId)}`), { headers });
  if (!resp.ok) {
    if (resp.status === 404) return { job: null };
    throw new Error(await resp.text() || `Job not found (${resp.status})`);
  }
  return await resp.json();
}

export async function getJobHistoryByRunId(
  podId: string,
  runId: string,
  limit = 25
): Promise<{ jobs: any[] }> {
  const headers = await authHeader();
  const resp = await fetch(
    apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/jobs/by-run/${encodeURIComponent(runId)}/history?limit=${encodeURIComponent(String(limit))}`),
    { headers }
  );
  if (!resp.ok) throw new Error(await resp.text() || `Job history failed (${resp.status})`);
  return await resp.json();
}

export async function getJobEvalResults(
  podId: string,
  jobId: string
): Promise<{ eval_results: any[] }> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/jobs/${encodeURIComponent(jobId)}/eval`), { headers });
  if (!resp.ok) throw new Error(await resp.text() || `Eval not found (${resp.status})`);
  return await resp.json();
}

export async function getJobLogTail(
  podId: string,
  jobId: string,
  tail = 200
): Promise<{ status: string; updated_at?: string; progress_percent?: number | null; tail_text?: string; error?: string | null }> {
  const headers = await authHeader();
  const resp = await fetch(
    apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/jobs/${encodeURIComponent(jobId)}/log?tail=${encodeURIComponent(String(tail))}`),
    { headers }
  );
  if (!resp.ok) throw new Error(await resp.text() || `Job log not found (${resp.status})`);
  return await resp.json();
}

