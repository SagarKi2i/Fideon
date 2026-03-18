import { useCallback, useEffect, useRef } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { emitDeviceRealtime, emitNotificationRealtime } from "@/lib/realtimeEvents";
import { safeLog } from "@/logger";
import { pushRealtimeNotification } from "@/lib/realtimeNotificationStore";

function getPodRequestMessage(eventType: string, payload: any): string {
  const modelName = payload?.new?.model_name || "pod request";
  if (eventType === "INSERT") return `New pod activation request: ${modelName}.`;
  const status = payload?.new?.status;
  if (status === "approved") return `Pod activation request approved: ${modelName}.`;
  if (status === "rejected") return `Pod activation request rejected: ${modelName}.`;
  return "A pod activation request was updated.";
}

function getPodRequestTargetPath(payload: any, currentUserId: string, currentRole: string | null): string {
  const isAdmin = isAdminRole(currentRole);
  const ownerId = payload?.new?.user_id || payload?.old?.user_id;
  const status = payload?.new?.status || payload?.old?.status;
  const requestId = payload?.new?.id || payload?.old?.id;

  if (isAdmin) {
    return requestId ? `/admin?podRequestId=${encodeURIComponent(String(requestId))}` : "/admin";
  }
  if (ownerId === currentUserId && (status === "approved" || status === "rejected")) {
    return requestId ? `/marketplace?requestId=${encodeURIComponent(String(requestId))}` : "/marketplace";
  }
  return "/marketplace";
}

function isAdminRole(role: string | null): boolean {
  return role === "admin" || role === "global_admin";
}

function shouldEmitPodRequestEvent(payload: any, currentUserId: string, currentRole: string | null): boolean {
  if (payload.eventType === "INSERT") return true;
  if (payload.eventType !== "UPDATE") return false;
  const prevStatus = payload.old?.status;
  const nextStatus = payload.new?.status;
  if (prevStatus === nextStatus) return false;
  if (!(nextStatus === "approved" || nextStatus === "rejected")) return false;

  // Outcome updates should reach request owner and admins/global admins.
  const ownerId = payload?.new?.user_id || payload?.old?.user_id;
  return ownerId === currentUserId || isAdminRole(currentRole);
}

function shouldReceivePodRequestNotification(payload: any, currentUserId: string, currentRole: string | null): boolean {
  if (payload.eventType === "INSERT") {
    return isAdminRole(currentRole);
  }
  const nextStatus = payload?.new?.status;
  if (nextStatus === "approved" || nextStatus === "rejected") {
    const ownerId = payload?.new?.user_id || payload?.old?.user_id;
    return ownerId === currentUserId || isAdminRole(currentRole);
  }
  return false;
}

function shouldEmitDecisionReviewEvent(payload: any, currentUserId: string, currentRole: string | null): boolean {
  if (payload.eventType === "INSERT") return true;
  if (payload.eventType !== "UPDATE") return false;
  const prevStatus = payload.old?.status;
  const nextStatus = payload.new?.status;
  if (prevStatus === nextStatus) return false;
  if (!(nextStatus === "approved" || nextStatus === "rejected")) return false;
  const ownerId = payload?.new?.user_id || payload?.old?.user_id;
  return ownerId === currentUserId || isAdminRole(currentRole);
}

function shouldReceiveDecisionReviewNotification(payload: any, currentUserId: string, currentRole: string | null): boolean {
  if (payload.eventType === "INSERT") {
    return isAdminRole(currentRole);
  }
  const nextStatus = payload?.new?.status;
  if (nextStatus === "approved" || nextStatus === "rejected") {
    const ownerId = payload?.new?.user_id || payload?.old?.user_id;
    return ownerId === currentUserId || isAdminRole(currentRole);
  }
  return false;
}

function getDecisionReviewMessage(eventType: string, payload: any): string {
  const title = payload?.new?.title || "review request";
  if (eventType === "INSERT") return `New decision review request: ${title}.`;
  const status = payload?.new?.status;
  if (status === "approved") return `Decision review approved: ${title}.`;
  if (status === "rejected") return `Decision review rejected: ${title}.`;
  return `Decision review "${title}" was updated.`;
}

function getDecisionReviewTargetPath(payload: any): string {
  const reviewId = payload?.new?.id || payload?.old?.id;
  const status = payload?.new?.status || payload?.old?.status;
  const tab = status === "approved" || status === "rejected" ? "completed" : "pending";
  if (!reviewId) return `/review-queue?tab=${tab}`;
  return `/review-queue?tab=${tab}&reviewId=${encodeURIComponent(String(reviewId))}`;
}

export function useGlobalRealtimeSubscriptions() {
  const { toast } = useToast();
  const channelsRef = useRef<RealtimeChannel[]>([]);
  const currentUserIdRef = useRef<string | null>(null);
  const currentRoleRef = useRef<string | null>(null);
  const realtimeEnabled = process.env.NEXT_PUBLIC_ENABLE_GLOBAL_REALTIME !== "false";

  const cleanupChannels = useCallback(() => {
    for (const channel of channelsRef.current) {
      supabase.removeChannel(channel);
    }
    channelsRef.current = [];
  }, []);

  const startRealtimeForUser = useCallback(async (userId: string) => {
    if (currentUserIdRef.current === userId) return;

    cleanupChannels();
    currentUserIdRef.current = userId;
    try {
      const { data: roleRow } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", userId)
        .maybeSingle();
      currentRoleRef.current = typeof roleRow?.role === "string" ? roleRow.role : null;
    } catch {
      currentRoleRef.current = null;
    }

    const deviceChannel = supabase
      .channel("global-device-status-live")
      .on("postgres_changes", { event: "*", schema: "public", table: "devices" }, (payload: any) => {
        if (
          payload.eventType === "UPDATE" &&
          payload.old?.status === payload.new?.status
        ) {
          return;
        }
        emitDeviceRealtime({
          eventType: payload.eventType,
          table: "devices",
          payload,
        });
      })
      .subscribe((status, err) => {
        safeLog.info("realtime_channel_status", {
          channel: "global-device-status-live",
          status,
          error: err?.message,
        });
      });

    const notificationsChannel = supabase
      .channel("global-notifications-live")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "pod_activation_requests" },
        (payload: any) => {
          const uid = currentUserIdRef.current;
          if (!uid) return;
          const role = currentRoleRef.current;
          if (!shouldEmitPodRequestEvent(payload, uid, role)) return;
          if (!shouldReceivePodRequestNotification(payload, uid, role)) return;
          const message = getPodRequestMessage(payload.eventType, payload);
          const detail = {
            eventType: payload.eventType,
            table: "pod_activation_requests" as const,
            payload,
            message,
            targetPath: getPodRequestTargetPath(payload, uid, role),
          };
          emitNotificationRealtime(detail);
          if (pushRealtimeNotification(detail)) {
            toast({ title: "Notification", description: message });
          }
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "decision_reviews" },
        (payload: any) => {
          const uid = currentUserIdRef.current;
          if (!uid) return;
          const role = currentRoleRef.current;
          if (!shouldEmitDecisionReviewEvent(payload, uid, role)) return;
          if (!shouldReceiveDecisionReviewNotification(payload, uid, role)) return;
          const message = getDecisionReviewMessage(payload.eventType, payload);
          const detail = {
            eventType: payload.eventType,
            table: "decision_reviews" as const,
            payload,
            message,
            targetPath: getDecisionReviewTargetPath(payload),
          };
          emitNotificationRealtime(detail);
          if (pushRealtimeNotification(detail)) {
            toast({ title: "Notification", description: message });
          }
        },
      )
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "device_sync_logs",
          filter: "status=eq.failed",
        },
        (payload: any) => {
          const message = "Device sync failure detected.";
          const detail = {
            eventType: payload.eventType,
            table: "device_sync_logs" as const,
            payload,
            message,
            targetPath: "/devices",
          };
          emitNotificationRealtime(detail);
          if (pushRealtimeNotification(detail)) {
            toast({ title: "Sync Alert", description: message, variant: "destructive" });
          }
        },
      )
      .subscribe((status, err) => {
        safeLog.info("realtime_channel_status", {
          channel: "global-notifications-live",
          status,
          error: err?.message,
        });
      });

    channelsRef.current = [deviceChannel, notificationsChannel];
  }, [cleanupChannels, toast]);

  useEffect(() => {
    if (!realtimeEnabled) {
      safeLog.warn("global_realtime_disabled", {
        reason: "NEXT_PUBLIC_ENABLE_GLOBAL_REALTIME=false",
      });
      return;
    }

    let active = true;

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!active) return;
      if (session?.user?.id) {
        void startRealtimeForUser(session.user.id);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (!active) return;
      if (event === "SIGNED_IN" && session?.user?.id) {
        void startRealtimeForUser(session.user.id);
      } else if (event === "SIGNED_OUT") {
        cleanupChannels();
        currentUserIdRef.current = null;
        currentRoleRef.current = null;
      }
    });

    return () => {
      active = false;
      subscription.unsubscribe();
      cleanupChannels();
      currentUserIdRef.current = null;
      currentRoleRef.current = null;
    };
  }, [cleanupChannels, realtimeEnabled, startRealtimeForUser]);
}
