/**
 * Thin wrapper that attaches the current session token to every backend API call.
 * Never calls Supabase PostgREST directly — all requests go to the FastAPI backend.
 *
 * backendFetch — always enforces a 15 s timeout (generous for staging / APIM cold-starts).
 * Pass `signal` from a useEffect AbortController to cancel on component unmount.
 */
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";

/** Default request timeout in milliseconds. */
const DEFAULT_TIMEOUT_MS = 15_000;

export async function getSessionToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export interface BackendFetchOptions extends RequestInit {
  /** External AbortSignal (e.g. from a useEffect cleanup controller). */
  signal?: AbortSignal;
  /** Override the built-in timeout. Pass 0 to disable. Default: 15 000 ms. */
  timeoutMs?: number;
}

/**
 * Fetch a backend endpoint with:
 *  - Automatic Bearer token from the current Supabase session
 *  - Built-in 15 s timeout (raises AbortError on timeout)
 *  - Combined abort: honours both the built-in timeout AND an external signal
 */
export async function backendFetch(
  path: string,
  options: BackendFetchOptions = {},
): Promise<Response> {
  const { signal: externalSignal, timeoutMs = DEFAULT_TIMEOUT_MS, ...rest } = options;

  const token = await getSessionToken();
  const headers: Record<string, string> = {
    ...(rest.headers as Record<string, string> | undefined ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (rest.body && typeof rest.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  // Build a combined signal: timeout + optional external signal.
  const signals: AbortSignal[] = [];
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  if (timeoutMs > 0) {
    const timeoutController = new AbortController();
    timeoutId = setTimeout(() => timeoutController.abort(), timeoutMs);
    signals.push(timeoutController.signal);
  }
  if (externalSignal) {
    signals.push(externalSignal);
  }

  // AbortSignal.any is available in modern browsers; fall back to first signal.
  const combinedSignal =
    signals.length === 0
      ? undefined
      : signals.length === 1
      ? signals[0]
      : typeof AbortSignal.any === "function"
      ? AbortSignal.any(signals)
      : signals[0];

  try {
    return await fetch(apiUrl(path), { ...rest, headers, signal: combinedSignal });
  } finally {
    if (timeoutId !== undefined) clearTimeout(timeoutId);
  }
}

/**
 * GET helper. Throws on non-2xx. AbortError propagates to the caller —
 * silence it in useEffect cleanup handlers.
 */
export async function backendGet<T = any>(
  path: string,
  options: Omit<BackendFetchOptions, "method" | "body"> = {},
): Promise<T> {
  const res = await backendFetch(path, options);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

export async function backendPost<T = any>(
  path: string,
  body: unknown,
  options: Omit<BackendFetchOptions, "method" | "body"> = {},
): Promise<T> {
  const res = await backendFetch(path, {
    ...options,
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

export async function backendPatch<T = any>(
  path: string,
  body: unknown,
  options: Omit<BackendFetchOptions, "method" | "body"> = {},
): Promise<T> {
  const res = await backendFetch(path, {
    ...options,
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.status}`);
  return res.json();
}

export async function backendDelete<T = any>(
  path: string,
  options: Omit<BackendFetchOptions, "method" | "body"> = {},
): Promise<T> {
  const res = await backendFetch(path, { ...options, method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`);
  return res.json();
}
