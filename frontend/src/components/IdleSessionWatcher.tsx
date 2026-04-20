"use client";

import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { getIdleSessionTimeoutMs, useIdleSessionTimeout } from "@/hooks/useIdleSessionTimeout";
import { useUserRole } from "@/hooks/useUserRole";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { safeLog } from "@/logger";

/**
 * Signs the user out after a period of UI inactivity (insurance-style session policy).
 * Duration: `NEXT_PUBLIC_IDLE_SESSION_MINUTES` (default 30). Set to `0` to disable.
 */
export function IdleSessionWatcher() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { role } = useUserRole();

  const handleIdle = useCallback(async () => {
    try {
      // Revoke session server-side (backend also writes the audit row).
      const { data: sessData } = await supabase.auth.getSession();
      const token = sessData.session?.access_token;
      if (token) {
        await fetch(apiUrl("/api/v1/auth/logout"), {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } catch (e) {
      safeLog.error("idle_backend_logout_error", {
        error: e instanceof Error ? e.message : String(e),
      });
    } finally {
      try {
        // Clear local session only — no extra server call.
        await supabase.auth.signOut({ scope: "local" });
      } catch (e) {
        safeLog.error("idle_sign_out_error", {
          error: e instanceof Error ? e.message : String(e),
        });
      }
    }

    toast({
      title: "Session ended",
      description:
        "You were signed out after a period of inactivity to protect your account.",
      variant: "destructive",
    });
    navigate("/auth", { replace: true });
  }, [navigate, toast, role]);

  const idleTimeoutEnabled = getIdleSessionTimeoutMs() !== null;
  useIdleSessionTimeout(handleIdle, idleTimeoutEnabled);

  return null;
}
