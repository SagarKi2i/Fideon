import { useState, useEffect, useRef } from 'react';
import type { User } from '@supabase/supabase-js';
import { supabase } from '@/integrations/supabase/client';
import type { Database } from '@/integrations/supabase/types';
import { apiUrl } from '@/lib/apiBaseUrl';
import { buildApiRequestError, readJsonSafe } from '@/lib/httpErrors';

type AppRole = Database['public']['Enums']['app_role'];

const VALID_APP_ROLES: AppRole[] = ['global_admin', 'admin', 'user', 'viewer', 'guest'];

function isAppRole(value: unknown): value is AppRole {
  return typeof value === 'string' && VALID_APP_ROLES.includes(value as AppRole);
}

async function resolveUserRole(token: string, signal: AbortSignal): Promise<AppRole> {
  try {
    const res = await fetch(apiUrl('/api/settings/profile'), {
      headers: { Authorization: `Bearer ${token}` },
      signal,
    });
    if (res.ok) {
      const payload = await readJsonSafe(res);
      const backendRole = payload?.profile?.role;
      if (isAppRole(backendRole)) {
        return backendRole;
      }
    } else if (res.status === 401 || res.status === 403) {
      const payload = await readJsonSafe(res);
      throw buildApiRequestError(res, payload, "Unable to resolve role");
    }
  } catch (backendError: any) {
    // Suppress abort errors — they are expected when the component unmounts
    // or when a newer fetch supersedes this one.
    if (backendError?.name !== 'AbortError') {
      console.error('Error resolving role via backend:', backendError);
    }
  }

  return 'user';
}

export function useUserRole() {
  const [role, setRole] = useState<AppRole | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Tracks the in-flight fetch so we can cancel it when a newer one starts
  // or when the component unmounts.
  const inflightRef = useRef<{ controller: AbortController; timer: ReturnType<typeof setTimeout> } | null>(null);

  useEffect(() => {
    function cancelInflight() {
      if (inflightRef.current) {
        clearTimeout(inflightRef.current.timer);
        inflightRef.current.controller.abort();
        inflightRef.current = null;
      }
    }

    async function fetchUserRole() {
      // Cancel any previous in-flight request before starting a new one.
      cancelInflight();

      try {
        const { data: { session } } = await supabase.auth.getSession();
        const sessionUser = session?.user ?? null;
        setUser(sessionUser);

        if (!sessionUser || !session?.access_token) {
          setRole(null);
          setLoading(false);
          return;
        }

        const controller = new AbortController();
        // 15 s — generous enough for cold-start staging backends / APIM overhead.
        const timer = setTimeout(() => controller.abort(), 15_000);
        inflightRef.current = { controller, timer };

        const resolvedRole = await resolveUserRole(session.access_token, controller.signal);

        clearTimeout(timer);
        inflightRef.current = null;

        setRole(resolvedRole);
      } catch (error: any) {
        if (error?.name !== 'AbortError') {
          console.error('Error in fetchUserRole:', error);
        }
        setRole(null);
      } finally {
        setLoading(false);
      }
    }

    fetchUserRole();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (!session?.user) {
        if (event === 'SIGNED_OUT') {
          cancelInflight();
          setUser(null);
          setRole(null);
          setLoading(false);
          return;
        }
        // TOKEN_REFRESH, INITIAL_SESSION with no user, etc. — re-resolve.
        fetchUserRole();
        return;
      }
      setUser(session.user);
      fetchUserRole();
    });

    return () => {
      cancelInflight();
      subscription.unsubscribe();
    };
  }, []);

  return {
    role,
    user,
    isAuthenticated: !!user,
    loading,
    isGlobalAdmin: role === 'global_admin',
    isAdmin: role === 'admin' || role === 'global_admin',
    isUser: role === 'user',
    isViewer: role === 'viewer',
    isGuest: role === 'guest',
  };
}
