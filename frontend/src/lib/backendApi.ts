/**
 * Thin wrapper that attaches the current session token to every backend API call.
 * Never calls Supabase PostgREST directly — all requests go to the FastAPI backend.
 */
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";

export async function getSessionToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function backendFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = await getSessionToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }
  return fetch(apiUrl(path), { ...options, headers });
}

export async function backendGet<T = any>(path: string): Promise<T> {
  const res = await backendFetch(path);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

export async function backendPost<T = any>(path: string, body: unknown): Promise<T> {
  const res = await backendFetch(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

export async function backendPatch<T = any>(path: string, body: unknown): Promise<T> {
  const res = await backendFetch(path, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.status}`);
  return res.json();
}

export async function backendDelete<T = any>(path: string): Promise<T> {
  const res = await backendFetch(path, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`);
  return res.json();
}
