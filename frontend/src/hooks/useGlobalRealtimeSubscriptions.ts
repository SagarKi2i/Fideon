import { useCallback, useEffect, useRef } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { emitDeviceRealtime, emitNotificationRealtime } from "@/lib/realtimeEvents";
import { safeLog } from "@/logger";
import { pushRealtimeNotification } from "@/lib/realtimeNotificationStore";
import { apiUrl } from "@/lib/apiBaseUrl";

const REALTIME_BACKOFF_BASE_MS = 1_000;
const REALTIME_BACKOFF_MAX_MS = 30_000;
const REALTIME_BACKOFF_JITTER_MS = 500;

type RealtimeChannelStatus =
  | "SUBSCRIBED"
  | "TIMED_OUT"
  | "CHANNEL_ERROR"
  | "CLOSED"
  | string;

// ─── Backend API helpers ───────────────────────────────────────────────────

async function getToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function backendGet(path: string): Promise<any> {
  const token = await getToken();
  if (!token) return null;
  const res = await fetch(apiUrl(path), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return null;
  return res.json();
}

async function backendPost(path: string, body: object): Promise<any> {
  const token = await getToken();
  if (!token) return null;
  const res = await fetch(apiUrl(path), {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) return null;
  return res.json();
}

// ─── Message builders ──────────────────────────────────────────────────────

function getPodRequestMessage(eventType: string, payload: any, requesterLabel?: string): string {
  const modelName = payload?.new?.model_name || "pod request";
  const ownerId = payload?.new?.user_id || payload?.old?.user_id;
  const ownerLabel = requesterLabel || (ownerId ? `user ${String(ownerId).slice(0, 8)}` : "a user");
  if (eventType === "INSERT") return `New pod activation request from ${ownerLabel}: ${modelName}.`;
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
  const ownerId = payload?.new?.user_id || payload?.old?.user_id;
  if (payload.eventType === "INSERT") {
    return isAdminRole(currentRole);
  }
  if (payload.eventType !== "UPDATE") return false;
  const prevStatus = payload.old?.status;
  const nextStatus = payload.new?.status;
  if (prevStatus === nextStatus) return false;
  if (!(nextStatus === "approved" || nextStatus === "rejected")) return false;
  return ownerId === currentUserId;
}

function shouldReceivePodRequestNotification(payload: any, currentUserId: string, currentRole: string | null): boolean {
  return shouldEmitPodRequestEvent(payload, currentUserId, currentRole);
}

function shouldEmitDecisionReviewEvent(payload: any, currentUserId: string, currentRole: string | null): boolean {
  const ownerId = payload?.new?.user_id || payload?.old?.user_id;
  if (payload.eventType === "INSERT") {
    return isAdminRole(currentRole);
  }
  if (payload.eventType !== "UPDATE") return false;
  const prevStatus = payload.old?.status;
  const nextStatus = payload.new?.status;
  if (prevStatus === nextStatus) return false;
  if (!(nextStatus === "approved" || nextStatus === "rejected")) return false;
  return ownerId === currentUserId;
}

function shouldReceiveDecisionReviewNotification(payload: any, currentUserId: string, currentRole: string | null): boolean {
  return shouldEmitDecisionReviewEvent(payload, currentUserId, currentRole);
}

function getDecisionReviewMessage(eventType: string, payload: any, requesterLabel?: string): string {
  const title = payload?.new?.title || "review request";
  const ownerId = payload?.new?.user_id || payload?.old?.user_id;
  const ownerLabel = requesterLabel || (ownerId ? `user ${String(ownerId).slice(0, 8)}` : "a user");
  if (eventType === "INSERT") return `New decision review request from ${ownerLabel}: ${title}.`;
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

type BacklogNotificationDetail = {
  eventType: "INSERT" | "UPDATE";
  table: "pod_activation_requests" | "decision_reviews";
  payload: any;
  message: string;
  targetPath: string;
};

// ─── Backend-based backlog builders ───────────────────────────────────────

async function buildBacklogNotifications(
  userId: string,
  role: string | null,
  resolveRequesterLabel: (userId: string | null | undefined) => Promise<string>
): Promise<BacklogNotificationDetail[]> {
  const data = await backendGet("/api/v1/notifications/backlog");
  if (!data) return [];

  const notifications: BacklogNotificationDetail[] = [];
  const isAdmin = data.is_admin as boolean;

  if (isAdmin) {
    for (const row of (data.pods ?? []) as any[]) {
      const requesterLabel = await resolveRequesterLabel(row.user_id);
      const payload = { eventType: "INSERT", new: row, old: null };
      notifications.push({
        eventType: "INSERT",
        table: "pod_activation_requests",
        payload,
        message: getPodRequestMessage("INSERT", payload, requesterLabel),
        targetPath: getPodRequestTargetPath(payload, userId, role),
      });
    }
    for (const row of (data.reviews ?? []) as any[]) {
      const requesterLabel = await resolveRequesterLabel(row.user_id);
      const payload = { eventType: "INSERT", new: row, old: null };
      notifications.push({
        eventType: "INSERT",
        table: "decision_reviews",
        payload,
        message: getDecisionReviewMessage("INSERT", payload, requesterLabel),
        targetPath: getDecisionReviewTargetPath(payload),
      });
    }
  } else {
    for (const row of (data.pods ?? []) as any[]) {
      const payload = { eventType: "UPDATE", new: row, old: { status: "pending", user_id: userId } };
      notifications.push({
        eventType: "UPDATE",
        table: "pod_activation_requests",
        payload,
        message: getPodRequestMessage("UPDATE", payload),
        targetPath: getPodRequestTargetPath(payload, userId, null),
      });
    }
    for (const row of (data.reviews ?? []) as any[]) {
      const payload = { eventType: "UPDATE", new: row, old: { status: "pending", user_id: userId } };
      notifications.push({
        eventType: "UPDATE",
        table: "decision_reviews",
        payload,
        message: getDecisionReviewMessage("UPDATE", payload),
        targetPath: getDecisionReviewTargetPath(payload),
      });
    }
  }

  return notifications;
}

export function useGlobalRealtimeSubscriptions() {
  const { toast } = useToast();
  const channelsRef = useRef<RealtimeChannel[]>([]);
  const currentUserIdRef = useRef<string | null>(null);
  const currentRoleRef = useRef<string | null>(null);
  const currentTenantIdRef = useRef<string | null>(null);
  const requesterLabelCacheRef = useRef<Record<string, string>>({});
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectInFlightRef = useRef(false);
  const realtimeEnabled = process.env.NEXT_PUBLIC_ENABLE_GLOBAL_REALTIME !== "false";

  const persistNotification = useCallback(async (userId: string, detail: {
    eventType: "INSERT" | "UPDATE" | "DELETE";
    table: "pod_activation_requests" | "device_sync_logs" | "decision_reviews";
    message: string;
    targetPath?: string;
    fingerprint: string;
  }) => {
    await backendPost("/api/v1/notifications", {
      user_id: userId,
      table_name: detail.table,
      event_type: detail.eventType,
      message: detail.message,
      target_path: detail.targetPath ?? null,
      source_fingerprint: detail.fingerprint,
    });
  }, []);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null && typeof window !== "undefined") {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const resetReconnectState = useCallback(() => {
    reconnectAttemptRef.current = 0;
    reconnectInFlightRef.current = false;
    clearReconnectTimer();
  }, [clearReconnectTimer]);

  const cleanupChannels = useCallback(() => {
    for (const channel of channelsRef.current) {
      supabase.removeChannel(channel);
    }
    channelsRef.current = [];
  }, []);

  // Resolve requester display label via backend (admin endpoint).
  const resolveRequesterLabel = useCallback(async (userId: string | null | undefined): Promise<string> => {
    if (!userId) return "a user";
    const cached = requesterLabelCacheRef.current[userId];
    if (cached) return cached;
    const fallback = `user ${String(userId).slice(0, 8)}`;
    try {
      const data = await backendGet(`/api/v1/users/${encodeURIComponent(userId)}/label`);
      const label = (data?.label as string) || fallback;
      requesterLabelCacheRef.current[userId] = label;
      return label;
    } catch {
      requesterLabelCacheRef.current[userId] = fallback;
      return fallback;
    }
  }, []);

  const startRealtimeForUser = useCallback(async (
    userId: string,
    options?: { force?: boolean }
  ) => {
    const force = options?.force === true;
    if (currentUserIdRef.current === userId && !force) return;

    cleanupChannels();
    currentUserIdRef.current = userId;

    // Resolve role and tenant_id via backend profile endpoint.
    try {
      const profileData = await backendGet("/api/settings/profile");
      const profile = profileData?.profile;
      currentRoleRef.current = profile?.role ?? null;
      currentTenantIdRef.current = profile?.tenant_id ?? null;
    } catch {
      currentRoleRef.current = null;
      currentTenantIdRef.current = null;
    }

    const handleRealtimeStatus = (channelName: string, status: RealtimeChannelStatus, err?: Error) => {
      safeLog.info("realtime_channel_status", {
        channel: channelName,
        status,
        error: err?.message,
      });

      if (status === "SUBSCRIBED") {
        reconnectAttemptRef.current = 0;
        reconnectInFlightRef.current = false;
        clearReconnectTimer();
        return;
      }

      if (!(status === "TIMED_OUT" || status === "CHANNEL_ERROR" || status === "CLOSED")) return;
      if (!currentUserIdRef.current || reconnectInFlightRef.current) return;

      reconnectInFlightRef.current = true;
      const attempt = reconnectAttemptRef.current + 1;
      reconnectAttemptRef.current = attempt;
      const backoff = Math.min(
        REALTIME_BACKOFF_MAX_MS,
        REALTIME_BACKOFF_BASE_MS * Math.pow(2, attempt - 1),
      );
      const jitter = Math.floor(Math.random() * REALTIME_BACKOFF_JITTER_MS);
      const delayMs = backoff + jitter;

      clearReconnectTimer();
      safeLog.warn("realtime_resubscribe_scheduled", {
        channel: channelName,
        status,
        attempt,
        delay_ms: delayMs,
      });

      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        const uid = currentUserIdRef.current;
        if (!uid) {
          reconnectInFlightRef.current = false;
          return;
        }
        void startRealtimeForUser(uid, { force: true }).finally(() => {
          reconnectInFlightRef.current = false;
        });
      }, delayMs);
    };

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
        handleRealtimeStatus("global-device-status-live", status, err);
      });

    const notificationsChannel = supabase
      .channel("global-notifications-live")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "pod_activation_requests" },
        async (payload: any) => {
          const uid = currentUserIdRef.current;
          if (!uid) return;
          const role = currentRoleRef.current;
          if (!shouldEmitPodRequestEvent(payload, uid, role)) return;
          if (!shouldReceivePodRequestNotification(payload, uid, role)) return;
          const requesterId = payload?.new?.user_id || payload?.old?.user_id;
          const requesterLabel =
            payload.eventType === "INSERT" ? await resolveRequesterLabel(requesterId) : undefined;
          const message = getPodRequestMessage(payload.eventType, payload, requesterLabel);
          const detail = {
            eventType: payload.eventType,
            table: "pod_activation_requests" as const,
            payload,
            message,
            targetPath: getPodRequestTargetPath(payload, uid, role),
          };
          emitNotificationRealtime(detail);
          const pushed = pushRealtimeNotification(detail);
          if (pushed) {
            void persistNotification(uid, {
              eventType: detail.eventType,
              table: detail.table,
              message: detail.message,
              targetPath: detail.targetPath,
              fingerprint: pushed.fingerprint,
            });
            toast({ title: "Notification", description: message });
          }
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "decision_reviews" },
        async (payload: any) => {
          const uid = currentUserIdRef.current;
          if (!uid) return;
          const role = currentRoleRef.current;
          if (!shouldEmitDecisionReviewEvent(payload, uid, role)) return;
          if (!shouldReceiveDecisionReviewNotification(payload, uid, role)) return;
          const requesterId = payload?.new?.user_id || payload?.old?.user_id;
          const requesterLabel =
            payload.eventType === "INSERT" ? await resolveRequesterLabel(requesterId) : undefined;
          const message = getDecisionReviewMessage(payload.eventType, payload, requesterLabel);
          const detail = {
            eventType: payload.eventType,
            table: "decision_reviews" as const,
            payload,
            message,
            targetPath: getDecisionReviewTargetPath(payload),
          };
          emitNotificationRealtime(detail);
          const pushed = pushRealtimeNotification(detail);
          if (pushed) {
            void persistNotification(uid, {
              eventType: detail.eventType,
              table: detail.table,
              message: detail.message,
              targetPath: detail.targetPath,
              fingerprint: pushed.fingerprint,
            });
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
          const uid = currentUserIdRef.current;
          const role = currentRoleRef.current;
          const tenantId = currentTenantIdRef.current;
          if (!uid || !isAdminRole(role)) return;
          const payloadTenantId = payload?.new?.tenant_id;
          if (tenantId && payloadTenantId && String(payloadTenantId) !== String(tenantId)) return;
          const message = "Device sync failure detected.";
          const detail = {
            eventType: payload.eventType,
            table: "device_sync_logs" as const,
            payload,
            message,
            targetPath: "/devices",
          };
          emitNotificationRealtime(detail);
          const pushed = pushRealtimeNotification(detail);
          if (pushed && uid) {
            void persistNotification(uid, {
              eventType: detail.eventType,
              table: detail.table,
              message: detail.message,
              targetPath: detail.targetPath,
              fingerprint: pushed.fingerprint,
            });
            toast({ title: "Sync Alert", description: message, variant: "destructive" });
          }
        },
      )
      .subscribe((status, err) => {
        handleRealtimeStatus("global-notifications-live", status, err);
      });

    channelsRef.current = [deviceChannel, notificationsChannel];
  }, [cleanupChannels, clearReconnectTimer, persistNotification, resolveRequesterLabel, toast]);

  useEffect(() => {
    if (!realtimeEnabled) {
      safeLog.warn("global_realtime_disabled", {
        reason: "NEXT_PUBLIC_ENABLE_GLOBAL_REALTIME=false",
      });
      return;
    }

    let active = true;

    const recoverRealtimeConnection = () => {
      const uid = currentUserIdRef.current;
      if (!uid) return;
      reconnectAttemptRef.current = 0;
      clearReconnectTimer();
      void startRealtimeForUser(uid, { force: true });
    };

    const handleOnline = () => {
      safeLog.info("realtime_reconnect_trigger", { reason: "browser_online" });
      recoverRealtimeConnection();
    };

    const handleVisibilityChange = () => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        safeLog.info("realtime_reconnect_trigger", { reason: "tab_visible" });
        recoverRealtimeConnection();
      }
    };

    if (typeof window !== "undefined") {
      window.addEventListener("online", handleOnline);
    }
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", handleVisibilityChange);
    }

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!active) return;
      if (session?.user?.id) {
        void startRealtimeForUser(session.user.id);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (!active) return;
      if (event === "SIGNED_IN" && session?.user?.id) {
        resetReconnectState();
        void startRealtimeForUser(session.user.id);
      } else if (event === "SIGNED_OUT") {
        resetReconnectState();
        cleanupChannels();
        currentUserIdRef.current = null;
        currentRoleRef.current = null;
        currentTenantIdRef.current = null;
      }
    });

    return () => {
      active = false;
      subscription.unsubscribe();
      resetReconnectState();
      cleanupChannels();
      currentUserIdRef.current = null;
      currentRoleRef.current = null;
      currentTenantIdRef.current = null;
      if (typeof window !== "undefined") {
        window.removeEventListener("online", handleOnline);
      }
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", handleVisibilityChange);
      }
    };
  }, [cleanupChannels, clearReconnectTimer, realtimeEnabled, resetReconnectState, startRealtimeForUser]);
}
