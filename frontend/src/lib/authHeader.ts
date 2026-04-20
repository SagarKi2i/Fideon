import { supabase } from "@/integrations/supabase/client";
import { notAuthenticatedError } from "@/lib/httpErrors";
import { apiUrl } from "@/lib/apiBaseUrl";

let _refreshInFlight: Promise<string | null> | null = null;

function isTokenExpired(accessToken: string): boolean {
  try {
    const payload = JSON.parse(atob(accessToken.split(".")[1]));
    return Date.now() >= payload.exp * 1000;
  } catch {
    return true;
  }
}

async function refreshViaBackend(refreshToken: string): Promise<string | null> {
  try {
    const res = await fetch(apiUrl("/api/v1/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const accessToken: string | null = data.access_token ?? null;
    const newRefresh: string | null = data.refresh_token ?? null;
    if (accessToken && newRefresh) {
      // Update the local Supabase session so the rest of the app sees the new tokens.
      await supabase.auth.setSession({ access_token: accessToken, refresh_token: newRefresh });
    }
    return accessToken;
  } catch {
    return null;
  }
}

async function getAccessTokenFresh(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const session = data.session;
  if (!session?.access_token) throw notAuthenticatedError();

  if (!isTokenExpired(session.access_token)) return session.access_token;

  if (!_refreshInFlight) {
    const refreshToken = session.refresh_token;
    _refreshInFlight = (async () => {
      try {
        if (!refreshToken) return null;
        return await refreshViaBackend(refreshToken);
      } catch (e: any) {
        const msg = String(e?.message || e || "");
        if (/lock broken|AbortError/i.test(msg)) return null;
        return null;
      } finally {
        _refreshInFlight = null;
      }
    })();
  }

  const token = await _refreshInFlight;
  if (token) return token;

  // Fallback: return cached token if any (backend may still accept it).
  const { data: again } = await supabase.auth.getSession();
  if (again.session?.access_token) return again.session.access_token;

  throw notAuthenticatedError();
}

export async function authHeader(): Promise<Record<string, string>> {
  const token = await getAccessTokenFresh();
  return { Authorization: `Bearer ${token}` };
}

export async function authHeadersJson(): Promise<Record<string, string>> {
  const base = await authHeader();
  return { ...base, "Content-Type": "application/json" };
}
