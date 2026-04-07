import { apiUrl } from "@/lib/apiBaseUrl";
import { authHeader, authHeadersJson } from "@/lib/authHeader";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";

export type TrainingJobRow = {
  id: string;
  created_at: string;
  updated_at: string;
  run_id: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  log_path?: string | null;
};

export type JobLogTail = {
  job_id: string;
  status: string;
  updated_at?: string | null;
  progress_percent?: number | null;
  tail_text: string;
  error?: string | null;
};

export async function fetchAcordJobs(input?: {
  status?: string;
  page?: number;
  limit?: number;
}): Promise<TrainingJobRow[]> {
  const qs = new URLSearchParams();
  if (input?.status) qs.set("status", input.status);
  if (input?.page) qs.set("page", String(input.page));
  if (input?.limit) qs.set("limit", String(input.limit));
  const res = await fetch(apiUrl(`/api/acord/admin/jobs${qs.toString() ? `?${qs}` : ""}`), {
    headers: await authHeader(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to load ACORD training jobs");
  return (payload.jobs || []) as TrainingJobRow[];
}

export async function fetchAcordJobLogTail(jobId: string, tailLines = 400): Promise<JobLogTail> {
  const res = await fetch(apiUrl(`/api/acord/admin/jobs/${encodeURIComponent(jobId)}/log?tail=${tailLines}`), {
    headers: await authHeader(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to load ACORD job logs");
  return payload as JobLogTail;
}

export async function fetchPodJobs(podId: string, input?: { status?: string; page?: number; limit?: number }): Promise<TrainingJobRow[]> {
  const qs = new URLSearchParams();
  if (input?.status) qs.set("status", input.status);
  if (input?.page) qs.set("page", String(input.page));
  if (input?.limit) qs.set("limit", String(input.limit));
  const res = await fetch(apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/jobs${qs.toString() ? `?${qs}` : ""}`), {
    headers: await authHeader(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to load Pod training jobs");
  return (payload.jobs || []) as TrainingJobRow[];
}

export async function fetchPodJobLogTail(podId: string, jobId: string, tailLines = 400): Promise<JobLogTail> {
  const res = await fetch(
    apiUrl(`/api/pods/${encodeURIComponent(podId)}/admin/jobs/${encodeURIComponent(jobId)}/log?tail=${tailLines}`),
    { headers: await authHeader() },
  );
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to load Pod job logs");
  return payload as JobLogTail;
}

export async function emitWebhookTestEvent(event_type: string, payload?: Record<string, unknown>): Promise<void> {
  const res = await fetch(apiUrl("/api/v1/webhooks/test-event"), {
    method: "POST",
    headers: await authHeadersJson(),
    body: JSON.stringify({ event_type, payload: payload || {} }),
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, body, "Failed to emit test event");
}

