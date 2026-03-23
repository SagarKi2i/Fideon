"use client";

import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { getIdleSessionTimeoutMs, useIdleSessionTimeout } from "@/hooks/useIdleSessionTimeout";
import { useUserRole } from "@/hooks/useUserRole";
import { supabase } from "@/integrations/supabase/client";
import { computeAuditIntegrityHash } from "@/lib/auditHash";
import { safeLog } from "@/logger";

/**
 * Signs the user out after a period of UI inactivity (insurance-style session policy).
 * Duration: `NEXT_PUBLIC_IDLE_SESSION_MINUTES` (default 15). Set to `0` to disable.
 */
export function IdleSessionWatcher() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { role } = useUserRole();

  const handleIdle = useCallback(async () => {
    const { data: { user } } = await supabase.auth.getUser();
    const currentRole = role;

    try {
      if (user) {
        try {
          const createdAt = new Date().toISOString();
          const integrity_hash = await computeAuditIntegrityHash({
            user_id: user.id,
            role: currentRole || "user",
            event: "session_timeout",
            action_code: "E",
            outcome_code: 0,
            resource_type: "auth_session",
            resource_id: null,
            created_at: createdAt,
          });

          await (supabase as any).from("auth_audit").insert({
              user_id: user.id,
              email: user.email,
              role: currentRole || "user",
              event: "session_timeout",
              action_code: "E",
              outcome_code: 0,
              resource_type: "auth_session",
              resource_id: null,
              created_at: createdAt,
              integrity_hash,
            });
        } catch (auditError) {
          safeLog.error("auth_audit_session_timeout_error", {
            error: auditError instanceof Error ? auditError.message : String(auditError),
          });
        }
      }
    } finally {
      try {
        await supabase.auth.signOut();
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
