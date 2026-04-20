/**
 * UserRoleContext — single source of truth for the authenticated user's role.
 *
 * Resolution order (fastest to slowest):
 *
 *   1. JWT fast path — role embedded in app_metadata by the Supabase Auth Hook.
 *      Zero HTTP calls, available instantly from the cached token.
 *
 *   2. HTTP fallback — for tokens issued before the hook was deployed.
 *      Calls /api/settings/profile with a 15 s per-attempt timeout.
 *      Retries once after 3 s if the first attempt returns the 'user' fallback
 *      (covers Azure cold-start where the backend isn't ready immediately).
 *
 * All 10+ components that previously called useUserRole() independently now
 * share this single provider — one fetch, one result, zero concurrent aborts.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  ReactNode,
} from "react";
import type { User } from "@supabase/supabase-js";
import { supabase } from "@/integrations/supabase/client";
import type { Database } from "@/integrations/supabase/types";
import { apiUrl } from "@/lib/apiBaseUrl";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";

type AppRole = Database["public"]["Enums"]["app_role"];

const VALID_APP_ROLES: AppRole[] = [
  "global_admin",
  "admin",
  "user",
  "viewer",
  "guest",
];

function isAppRole(value: unknown): value is AppRole {
  return (
    typeof value === "string" && VALID_APP_ROLES.includes(value as AppRole)
  );
}

// ---------------------------------------------------------------------------
// Per-attempt fetch (owns its own 15 s timeout, respects lifecycle signal)
// ---------------------------------------------------------------------------

async function resolveOnce(
  token: string,
  lifecycleSignal: AbortSignal,
): Promise<AppRole> {
  // Each attempt gets its own timeout controller so a retry can have a fresh
  // 15 s window even if the previous attempt already timed out.
  const timeoutCtrl = new AbortController();
  const timer = setTimeout(() => timeoutCtrl.abort(), 15_000);

  const combined =
    typeof AbortSignal.any === "function"
      ? AbortSignal.any([lifecycleSignal, timeoutCtrl.signal])
      : timeoutCtrl.signal; // older browsers: timeout only

  try {
    const res = await fetch(apiUrl("/api/settings/profile"), {
      headers: { Authorization: `Bearer ${token}` },
      signal: combined,
    });

    if (res.ok) {
      const payload = await readJsonSafe(res);
      const backendRole = payload?.profile?.role;
      if (isAppRole(backendRole)) return backendRole;
    } else if (res.status === 401 || res.status === 403) {
      const payload = await readJsonSafe(res);
      // Auth errors are terminal — propagate so the caller can clear state.
      throw buildApiRequestError(res, payload, "Unable to resolve role");
    }
  } catch (err: any) {
    // If the LIFECYCLE was aborted (unmount / superseded call), re-throw so
    // fetchUserRole's catch block can handle it and skip setRole.
    if (lifecycleSignal.aborted) throw err;
    // Per-attempt timeout or transient network error — fall through to 'user'.
    if (err?.name !== "AbortError") {
      console.error("Error resolving role via backend:", err);
    }
  } finally {
    clearTimeout(timer);
  }

  return "user"; // fallback
}

// ---------------------------------------------------------------------------
// Retry wrapper — one retry after 3 s if first attempt returned the fallback
// ---------------------------------------------------------------------------

async function resolveWithRetry(
  token: string,
  lifecycleSignal: AbortSignal,
): Promise<AppRole> {
  const first = await resolveOnce(token, lifecycleSignal);

  // Don't retry if: resolved correctly, or lifecycle was cancelled.
  if (first !== "user" || lifecycleSignal.aborted) return first;

  // Wait 3 s before the second attempt. Cancel the wait if lifecycle fires.
  await new Promise<void>((resolve) => {
    const t = setTimeout(resolve, 3_000);
    lifecycleSignal.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        resolve();
      },
      { once: true },
    );
  });

  if (lifecycleSignal.aborted) return "user";

  return resolveOnce(token, lifecycleSignal);
}

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface UserRoleContextValue {
  role: AppRole | null;
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  isGlobalAdmin: boolean;
  isAdmin: boolean;
  isUser: boolean;
  isViewer: boolean;
  isGuest: boolean;
}

const UserRoleContext = createContext<UserRoleContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function UserRoleProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<AppRole | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Tracks the active lifecycle controller so we can cancel it when a newer
  // fetchUserRole() call starts or when the provider unmounts.
  const inflightRef = useRef<AbortController | null>(null);

  useEffect(() => {
    function cancelInflight() {
      if (inflightRef.current) {
        inflightRef.current.abort();
        inflightRef.current = null;
      }
    }

    async function fetchUserRole() {
      cancelInflight();

      let lifecycle: AbortController | null = null;

      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        const sessionUser = session?.user ?? null;
        setUser(sessionUser);

        if (!sessionUser || !session?.access_token) {
          setRole(null);
          setLoading(false);
          return;
        }

        // ── FAST PATH ────────────────────────────────────────────────────────
        // The Supabase Auth Hook embeds the role in every JWT at issue time.
        // Read it directly — zero HTTP calls, zero latency.
        const jwtRole = sessionUser.app_metadata?.role;
        if (isAppRole(jwtRole)) {
          setRole(jwtRole);
          setLoading(false);
          return;
        }

        // ── SLOW PATH ────────────────────────────────────────────────────────
        // JWT predates the Auth Hook (or hook not yet registered).
        // Fall back to the profile API with one retry on failure.
        lifecycle = new AbortController();
        inflightRef.current = lifecycle;

        const resolvedRole = await resolveWithRetry(
          session.access_token,
          lifecycle.signal,
        );

        // Staleness guard: if a newer call already committed its result, bail.
        if (inflightRef.current !== lifecycle) return;

        inflightRef.current = null;
        setRole(resolvedRole);
      } catch (err: any) {
        if (err?.name !== "AbortError") {
          console.error("Error in fetchUserRole:", err);
        }
        setRole(null);
      } finally {
        setLoading(false);
      }
    }

    // Initial load — one fetch on mount.
    fetchUserRole();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      // INITIAL_SESSION fires on startup with the stored session — the mount
      // fetchUserRole() above already handles this, so skip it here.
      if (event === "INITIAL_SESSION") return;

      // TOKEN_REFRESHED: same user, new token.
      // Re-read the JWT role in case the hook added/updated it in the new token.
      if (event === "TOKEN_REFRESHED") {
        if (session?.user) {
          setUser(session.user);
          const jwtRole = session.user.app_metadata?.role;
          if (isAppRole(jwtRole)) {
            setRole(jwtRole);
            return;
          }
          // New token still missing the JWT claim — re-fetch from API.
          fetchUserRole();
        }
        return;
      }

      // SIGNED_OUT / USER_DELETED — clear everything.
      if (!session?.user) {
        cancelInflight();
        setUser(null);
        setRole(null);
        setLoading(false);
        return;
      }

      // SIGNED_IN (actual login) — fetch role for the new user.
      setUser(session.user);
      fetchUserRole();
    });

    return () => {
      cancelInflight();
      subscription.unsubscribe();
    };
  }, []);

  const value: UserRoleContextValue = {
    role,
    user,
    loading,
    isAuthenticated: !!user,
    isGlobalAdmin: role === "global_admin",
    isAdmin: role === "admin" || role === "global_admin",
    isUser: role === "user",
    isViewer: role === "viewer",
    isGuest: role === "guest",
  };

  return (
    <UserRoleContext.Provider value={value}>
      {children}
    </UserRoleContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook — drop-in replacement, zero changes needed in consumers
// ---------------------------------------------------------------------------

export function useUserRole(): UserRoleContextValue {
  const ctx = useContext(UserRoleContext);
  if (!ctx) {
    throw new Error("useUserRole must be used inside <UserRoleProvider>");
  }
  return ctx;
}
