import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { buildApiRequestError, notAuthenticatedError, readJsonSafe } from "@/lib/httpErrors";

export interface ModelRegistryRow {
  id: string;
  tenant_id: string | null;
  task_key: string;
  task_label: string;
  base_model: string;
  display_name: string | null;
  bleu_score: number | null;
  f1_score: number | null;
  latency_ms: number | null;
  is_best_for_task: boolean;
  mlflow_run_id: string | null;
  mlflow_experiment_id: string | null;
  source: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

async function authHeadersJson(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw notAuthenticatedError();
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export async function fetchModelRegistry(taskKey?: string): Promise<ModelRegistryRow[]> {
  const q = taskKey ? `?task_key=${encodeURIComponent(taskKey)}` : "";
  const res = await fetch(apiUrl(`/api/v1/model-registry${q}`), {
    headers: await authHeadersJson(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to load model registry");
  return (payload.models || []) as ModelRegistryRow[];
}

export async function recomputeModelRegistryBest(): Promise<{ buckets_updated?: number }> {
  const res = await fetch(apiUrl("/api/v1/model-registry/recompute-best"), {
    method: "POST",
    headers: await authHeadersJson(),
    body: "{}",
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to recompute best models");
  return payload as { buckets_updated?: number };
}

export async function syncModelRegistryFromMlflow(): Promise<{
  inserted?: number;
  updated?: number;
  experiments_scanned?: number;
  runs_fetched?: number;
  message?: string;
}> {
  const res = await fetch(apiUrl("/api/v1/model-registry/sync-mlflow"), {
    method: "POST",
    headers: await authHeadersJson(),
    body: "{}",
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "MLflow sync failed");
  return payload as {
    inserted?: number;
    updated?: number;
    experiments_scanned?: number;
    runs_fetched?: number;
    message?: string;
  };
}
