import { useState, useEffect } from 'react';
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

async function resolveUserRole(userId: string): Promise<AppRole> {
  const { data, error } = await (supabase as any)
    .from('user_roles')
    .select('role')
    .eq('user_id', userId)
    .maybeSingle();

  if (!error && isAppRole(data?.role)) {
    return data.role;
  }

  try {
    const { data: sessionData } = await supabase.auth.getSession();
    const token = sessionData.session?.access_token;
    if (token) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      try {
        const res = await fetch(apiUrl('/api/settings/profile'), {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        clearTimeout(timeout);
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
      } finally {
        clearTimeout(timeout);
      }
    }
  } catch (backendError) {
    console.error('Error resolving role via backend:', backendError);
  }

  return 'user';
}

export function useUserRole() {
  const [role, setRole] = useState<AppRole | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchUserRole() {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        setUser(user);

        if (!user) {
          setRole(null);
          setLoading(false);
          return;
        }

        const resolvedRole = await resolveUserRole(user.id);
        setRole(resolvedRole);
      } catch (error) {
        console.error('Error in fetchUserRole:', error);
        setRole(null);
      } finally {
        setLoading(false);
      }
    }

    fetchUserRole();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      // Keep user during transient auth churn. Only clear on explicit terminal events.
      if (!session?.user) {
        if (event === "SIGNED_OUT") {
          setUser(null);
          setRole(null);
          setLoading(false);
          return;
        }
        // For INITIAL_SESSION/TOKEN_REFRESH_FAILED/etc, preserve current user state.
        fetchUserRole();
        return;
      }
      setUser(session.user);
      fetchUserRole();
    });

    return () => subscription.unsubscribe();
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
