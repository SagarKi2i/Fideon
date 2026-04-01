import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";

export type AcordExtractResponse = {
  run_id: string;
  status: string;
  overall_confidence: number;
  extracted: any;
  /** True when extraction worked but saving the draft run failed (e.g. Supabase). Fields are still returned. */
  partial?: boolean;
  persist_error?: string | null;
  warning?: string | null;
};

type AcordExtractStartResponse = {
  job_id: string;
  status: string;
};

type AcordExtractJobStatusResponse = {
  job_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  result?: AcordExtractResponse | null;
  error?: string | null;
};

const LOG = "[acordWorkflowApi]";
let _refreshInFlight: Promise<string | null> | null = null;
const ACORD_STATUS_POLL_MS = 30_000;
const ACORD_STATUS_TIMEOUT_MS = 30 * 60 * 1000;

/** Returns true if the JWT access token's exp claim is in the past. */
function isTokenExpired(accessToken: string): boolean {
  try {
    const payload = JSON.parse(atob(accessToken.split(".")[1]));
    const expiredAt = new Date(payload.exp * 1000);
    const expired = Date.now() >= payload.exp * 1000;
    console.debug(`${LOG} isTokenExpired: exp=${expiredAt.toISOString()} expired=${expired}`);
    return expired;
  } catch {
    console.warn(`${LOG} isTokenExpired: could not decode token — treating as expired`);
    return true;
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) {
    console.error(`${LOG} authHeader: no session — user is not authenticated`);
    throw new Error("Not authenticated");
  }

  // Avoid lock-contention/race errors from concurrent refreshSession() calls.
  if (!isTokenExpired(session.access_token)) {
    return { Authorization: `Bearer ${session.access_token}` };
  }

  if (!_refreshInFlight) {
    _refreshInFlight = (async () => {
      try {
        console.debug(`${LOG} authHeader: token expired, attempting single-flight refresh`);
        const { data: { session: refreshed }, error } = await supabase.auth.refreshSession();
        if (error || !refreshed) return null;
        return refreshed.access_token;
      } catch (e: any) {
        const msg = String(e?.message || e || "");
        // Seen in browsers with lock races: "AbortError: Lock broken by another request with the 'steal' option."
        if (/lock broken|AbortError/i.test(msg)) return null;
        return null;
      } finally {
        _refreshInFlight = null;
      }
    })();
  }

  const token = await _refreshInFlight;
  if (token) return { Authorization: `Bearer ${token}` };

  // Last fallback: use existing token if still present; backend will reject if truly invalid.
  const { data: { session: cached } } = await supabase.auth.getSession();
  if (cached?.access_token) {
    return { Authorization: `Bearer ${cached.access_token}` };
  }
  throw new Error("Session expired — please sign out and sign back in.");
}

export async function extractAcord(
  file: File,
  formTypeHint?: string,
): Promise<AcordExtractResponse> {
  console.debug(`${LOG} extractAcord: file=${file.name} size=${file.size} formTypeHint=${formTypeHint ?? "none"}`);
  const headers = await authHeader();
  const formData = new FormData();
  formData.append("file", file);

  const startUrl = formTypeHint
    ? apiUrl(`/api/acord/extract/start?form_type_hint=${encodeURIComponent(formTypeHint)}`)
    : apiUrl("/api/acord/extract/start");

  console.debug(`${LOG} extractAcord: POST ${startUrl}`);
  let startResp: Response;
  try {
    startResp = await fetch(startUrl, { method: "POST", headers, body: formData });
  } catch (err: unknown) {
    const e = err as { name?: string; message?: string };
    if (
      e?.name === "TypeError" ||
      (typeof e?.message === "string" && /failed to fetch|networkerror|load failed/i.test(e.message))
    ) {
      throw new Error(
        "Network error while starting extraction job. Check backend URL/reachability.",
      );
    }
    throw err;
  }
  console.debug(`${LOG} extractAcord: start response status=${startResp.status}`);

  if (!startResp.ok) {
    const body = await startResp.text();
    if (startResp.status === 404) {
      // Backward compatibility: deployed backend may not have async endpoints yet.
      const syncUrl = formTypeHint
        ? apiUrl(`/api/acord/extract?form_type_hint=${encodeURIComponent(formTypeHint)}`)
        : apiUrl("/api/acord/extract");
      const syncResp = await fetch(syncUrl, { method: "POST", headers, body: formData });
      if (!syncResp.ok) {
        const syncBody = await syncResp.text();
        throw new Error(syncBody || `Extract failed (${syncResp.status})`);
      }
      return await syncResp.json();
    }
    if (startResp.status === 401) {
      console.error(
        `${LOG} extractAcord: start 401 Unauthorized — server response body: ${body}`,
      );
      throw new Error("Session expired — please sign out and sign back in.");
    }
    console.error(`${LOG} extractAcord: start error status=${startResp.status} body=${body}`);
    throw new Error(body || `Extract start failed (${startResp.status})`);
  }
  const startPayload = await startResp.json() as AcordExtractStartResponse;
  if (!startPayload?.job_id) {
    throw new Error("Extraction start failed: missing job id");
  }

  const statusUrl = apiUrl(`/api/acord/extract/status/${encodeURIComponent(startPayload.job_id)}`);
  const runSyncFallback = async (): Promise<AcordExtractResponse> => {
    const syncUrl = formTypeHint
      ? apiUrl(`/api/acord/extract?form_type_hint=${encodeURIComponent(formTypeHint)}`)
      : apiUrl("/api/acord/extract");
    const fallbackForm = new FormData();
    fallbackForm.append("file", file);
    const syncResp = await fetch(syncUrl, { method: "POST", headers, body: fallbackForm });
    if (!syncResp.ok) {
      const syncBody = await syncResp.text();
      throw new Error(syncBody || `Extract failed (${syncResp.status})`);
    }
    return await syncResp.json();
  };
  const deadline = Date.now() + ACORD_STATUS_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, ACORD_STATUS_POLL_MS));
    // Refresh auth header for long-running jobs; initial token can expire mid-poll.
    const pollHeaders = await authHeader();
    const pollResp = await fetch(statusUrl, { headers: pollHeaders });
    if (!pollResp.ok) {
      const body = await pollResp.text();
      // Multi-instance/restart case: async job cache can be missing on this node.
      // Fall back to sync extraction to avoid a hard user-facing failure.
      if (pollResp.status === 404 && /job not found/i.test(body)) {
        return await runSyncFallback();
      }
      throw new Error(body || `Extract status failed (${pollResp.status})`);
    }
    const st = await pollResp.json() as AcordExtractJobStatusResponse;
    if (st.status === "succeeded" && st.result) return st.result;
    if (st.status === "failed") {
      throw new Error(st.error || "Extraction job failed");
    }
  }
  throw new Error("Extraction timed out while waiting for async job");
}

export async function listUserRuns(
  page = 1,
  limit = 20,
  status?: string,
): Promise<{ runs: any[]; page: number; limit: number }> {
  const headers = await authHeader();
  let url = apiUrl(`/api/acord/runs?page=${page}&limit=${limit}`);
  if (status) url += `&status=${encodeURIComponent(status)}`;
  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error(await resp.text() || `List runs failed (${resp.status})`);
  return await resp.json();
}

export async function adminQueueStats(): Promise<Record<string, number>> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl("/api/acord/admin/queue/stats"), { headers });
  if (!resp.ok) throw new Error(await resp.text() || `Stats failed (${resp.status})`);
  return await resp.json();
}

export async function listTrainingJobs(
  page = 1,
  limit = 20,
  status?: string,
): Promise<{ jobs: any[]; page: number; limit: number }> {
  const headers = await authHeader();
  let url = apiUrl(`/api/acord/admin/jobs?page=${page}&limit=${limit}`);
  if (status) url += `&status=${encodeURIComponent(status)}`;
  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error(await resp.text() || `Jobs failed (${resp.status})`);
  return await resp.json();
}

export async function getTrainingJob(jobId: string): Promise<{ job: any }> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/acord/admin/jobs/${jobId}`), { headers });
  if (!resp.ok) throw new Error(await resp.text() || `Job not found (${resp.status})`);
  return await resp.json();
}

export async function getJobByRunId(runId: string): Promise<{ job: any } | { job: null }> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/acord/admin/jobs/by-run/${runId}`), { headers });
  if (!resp.ok) {
    if (resp.status === 404) return { job: null };
    throw new Error(await resp.text() || `Request failed (${resp.status})`);
  }
  return await resp.json();
}

export async function getJobHistoryByRunId(
  runId: string,
  limit = 25,
): Promise<{ jobs: any[] }> {
  const headers = await authHeader();
  const resp = await fetch(
    apiUrl(`/api/acord/admin/jobs/by-run/${runId}/history?limit=${encodeURIComponent(String(limit))}`),
    { headers },
  );
  if (!resp.ok) throw new Error(await resp.text() || `Job history failed (${resp.status})`);
  return await resp.json();
}

export async function getJobEvalResults(jobId: string): Promise<{ eval_results: any[] }> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/acord/admin/jobs/${jobId}/eval`), { headers });
  if (!resp.ok) throw new Error(await resp.text() || `Eval not found (${resp.status})`);
  return await resp.json();
}

export async function getJobLogTail(
  jobId: string,
  tail = 200,
): Promise<{
  status: string;
  updated_at?: string;
  progress_percent?: number | null;
  tail_text?: string;
  error?: string | null;
}> {
  const headers = await authHeader();
  const resp = await fetch(
    apiUrl(`/api/acord/admin/jobs/${jobId}/log?tail=${encodeURIComponent(String(tail))}`),
    { headers },
  );
  if (!resp.ok) throw new Error(await resp.text() || `Job log not found (${resp.status})`);
  return await resp.json();
}

export async function patchAdminQueueItem(
  runId: string,
  patch: { priority?: number; assigned_to?: string; state?: string },
): Promise<{ updated: Record<string, any> }> {
  const headers = { ...(await authHeader()), "Content-Type": "application/json" };
  const resp = await fetch(apiUrl(`/api/acord/admin/queue/${runId}/detail`), {
    method: "PATCH",
    headers,
    body: JSON.stringify(patch),
  });
  if (!resp.ok) throw new Error(await resp.text() || `Patch failed (${resp.status})`);
  return await resp.json();
}

export async function submitAcordRun(
  runId: string,
  body: {
    thumbs_up: boolean;
    notes?: string;
    corrected_json?: any;
    require_admin_approval_for_training?: boolean;
  }
): Promise<{ status: string }> {
  const headers = { ...(await authHeader()), "Content-Type": "application/json" };
  const resp = await fetch(apiUrl(`/api/acord/runs/${runId}/submit`), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text();
    if (resp.status === 401) {
      throw new Error("Session expired — please sign in again.");
    }
    throw new Error(text || `Submit failed (${resp.status})`);
  }
  return await resp.json();
}

export async function reExtractRun(
  runId: string,
  formTypeHint?: string,
  file?: File,
): Promise<AcordExtractResponse> {
  const headers = await authHeader();
  const formData = new FormData();
  formData.append("body", JSON.stringify({ form_type_hint: formTypeHint ?? null }));
  if (file) formData.append("file", file);

  // Send as JSON body since file is optional — use query params for form_type_hint
  const params = new URLSearchParams();
  if (formTypeHint) params.set("form_type_hint", formTypeHint);

  // POST with JSON body (no file)
  const url = apiUrl(`/api/acord/runs/${runId}/re-extract`);
  const resp = await fetch(url, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ form_type_hint: formTypeHint ?? null }),
  });
  if (!resp.ok) throw new Error(await resp.text() || `Re-extract failed (${resp.status})`);
  return await resp.json();
}

export async function getAcordRun(runId: string): Promise<any> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/acord/runs/${runId}`), { headers });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `Get run failed (${resp.status})`);
  }
  return await resp.json();
}

/** Same JSONL object as `fine_tuning.export_approved_acord_dataset` (six-field output, clean metadata). */
export async function previewTrainingJsonl(
  runId: string,
  body: {
    extracted_json: Record<string, unknown>;
    raw_text: string;
    source_filename?: string | null;
  },
): Promise<{ record: Record<string, unknown> }> {
  const headers = { ...(await authHeader()), "Content-Type": "application/json" };
  const resp = await fetch(apiUrl(`/api/acord/runs/${runId}/preview-training-jsonl`), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `Training preview failed (${resp.status})`);
  }
  return await resp.json();
}

export async function getRunHealthCard(runId: string): Promise<{
  run: any;
  confidence_evaluation: any;
  latest_training_job: any;
  latest_eval_results: any[];
  quality_gate_snapshot: any;
}> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/acord/admin/runs/${runId}/health-card`), { headers });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `Health card failed (${resp.status})`);
  }
  return await resp.json();
}

export type AdminQueueFilters = {
  states?: string;        // comma-separated, e.g. "open,in_progress"
  form_type?: string;
  conf_min?: number;
  conf_max?: number;
  order_by?: "priority" | "created_at" | "updated_at";
  order_dir?: "asc" | "desc";
  page?: number;
  limit?: number;
};

export async function listAcordAdminQueue(
  filters: AdminQueueFilters = {},
): Promise<{ queue: any[]; page: number; limit: number }> {
  const headers = await authHeader();
  const params = new URLSearchParams();
  if (filters.states)    params.set("states",    filters.states);
  if (filters.form_type) params.set("form_type", filters.form_type);
  if (filters.conf_min != null) params.set("conf_min", String(filters.conf_min));
  if (filters.conf_max != null) params.set("conf_max", String(filters.conf_max));
  if (filters.order_by)  params.set("order_by",  filters.order_by);
  if (filters.order_dir) params.set("order_dir", filters.order_dir);
  if (filters.page)      params.set("page",      String(filters.page));
  if (filters.limit)     params.set("limit",     String(filters.limit));

  const qs = params.toString();
  const resp = await fetch(apiUrl(`/api/acord/admin/queue${qs ? `?${qs}` : ""}`), { headers });
  if (!resp.ok) throw new Error(await resp.text() || `Queue failed (${resp.status})`);
  const data = await resp.json();
  return { queue: data.queue || [], page: data.page ?? 1, limit: data.limit ?? 25 };
}

export async function batchReviewAcordRuns(
  runIds: string[],
  decision: "approve" | "reject",
  notes?: string,
): Promise<{ decision: string; succeeded: number; total: number; results: any[] }> {
  const headers = { ...(await authHeader()), "Content-Type": "application/json" };
  const resp = await fetch(apiUrl("/api/acord/admin/batch-review"), {
    method: "POST",
    headers,
    body: JSON.stringify({ run_ids: runIds, decision, notes }),
  });
  if (!resp.ok) throw new Error(await resp.text() || `Batch review failed (${resp.status})`);
  return await resp.json();
}

export async function adminReviewAcordRun(
  runId: string,
  body: { decision: "approve" | "rework" | "reject"; notes?: string; corrected_json?: any }
): Promise<{ status: string }> {
  const headers = { ...(await authHeader()), "Content-Type": "application/json" };
  const resp = await fetch(apiUrl(`/api/acord/admin/${runId}/review`), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `Admin review failed (${resp.status})`);
  }
  return await resp.json();
}

