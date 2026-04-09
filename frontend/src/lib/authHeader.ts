import { supabase } from "@/integrations/supabase/client";
import { notAuthenticatedError } from "@/lib/httpErrors";

let _refreshInFlight: Promise<string | null> | null = null;

function isTokenExpired(accessToken: string): boolean {
  try {
    const payload = JSON.parse(atob(accessToken.split(".")[1]));
    return Date.now() >= payload.exp * 1000;
  } catch {
    return true;
  }
}

async function getAccessTokenFresh(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const session = data.session;
  if (!session?.access_token) throw notAuthenticatedError();

  if (!isTokenExpired(session.access_token)) return session.access_token;

  if (!_refreshInFlight) {
    _refreshInFlight = (async () => {
      try {
        const { data: refreshed, error } = await supabase.auth.refreshSession();
        if (error || !refreshed.session?.access_token) return null;
        return refreshed.session.access_token;
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

