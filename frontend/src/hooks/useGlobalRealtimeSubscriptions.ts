import { useCallback, useEffect, useRef } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { emitDeviceRealtime, emitNotificationRealtime } from "@/lib/realtimeEvents";
import { safeLog } from "@/logger";
import { pushRealtimeNotification } from "@/lib/realtimeNotificationStore";

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
    // New requests should notify admin/global_admin reviewers.
    return isAdminRole(currentRole);
  }
  if (payload.eventType !== "UPDATE") return false;
  const prevStatus = payload.old?.status;
  const nextStatus = payload.new?.status;
  if (prevStatus === nextStatus) return false;
  if (!(nextStatus === "approved" || nextStatus === "rejected")) return false;
  // Outcomes should notify only the requester.
  return ownerId === currentUserId;
}

function shouldReceivePodRequestNotification(payload: any, currentUserId: string, currentRole: string | null): boolean {
  return shouldEmitPodRequestEvent(payload, currentUserId, currentRole);
}

function shouldEmitDecisionReviewEvent(payload: any, currentUserId: string, currentRole: string | null): boolean {
  const ownerId = payload?.new?.user_id || payload?.old?.user_id;
  if (payload.eventType === "INSERT") {
    // New review requests should notify admin/global_admin reviewers.
    return isAdminRole(currentRole);
  }
  if (payload.eventType !== "UPDATE") return false;
  const prevStatus = payload.old?.status;
  const nextStatus = payload.new?.status;
  if (prevStatus === nextStatus) return false;
  if (!(nextStatus === "approved" || nextStatus === "rejected")) return false;
  // Outcomes should notify only the requester.
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

async function fetchRecentAdminBacklog(recentIso: string) {
  return Promise.all([
    supabase
      .from("pod_activation_requests")
      .select("id,user_id,model_name,status,requested_at")
      .gte("requested_at", recentIso)
      .order("requested_at", { ascending: false })
      .limit(20),
    supabase
      .from("decision_reviews")
      .select("id,user_id,title,status,created_at")
      .gte("created_at", recentIso)
      .order("created_at", { ascending: false })
      .limit(20),
  ]);
}

async function fetchRecentUserOutcomes(userId: string) {
  return Promise.all([
    supabase
      .from("pod_activation_requests")
      .select("id,user_id,model_name,status,reviewed_at")
      .eq("user_id", userId)
      .in("status", ["approved", "rejected"])
      .order("reviewed_at", { ascending: false })
      .limit(20),
    supabase
      .from("decision_reviews")
      .select("id,user_id,title,status,reviewed_at")
      .eq("user_id", userId)
      .in("status", ["approved", "rejected"])
      .order("reviewed_at", { ascending: false })
      .limit(20),
  ]);
}

async function buildAdminBacklogNotifications(
  userId: string,
  role: string | null,
  resolveRequesterLabel: (userId: string | null | undefined) => Promise<string>
): Promise<BacklogNotificationDetail[]> {
  const recentIso = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  const [{ data: recentPodRequests, error: podError }, { data: recentReviews, error: reviewError }] =
    await fetchRecentAdminBacklog(recentIso);

  const notifications: BacklogNotificationDetail[] = [];
  if (!podError && Array.isArray(recentPodRequests)) {
    for (const row of recentPodRequests) {
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
  }
  if (!reviewError && Array.isArray(recentReviews)) {
    for (const row of recentReviews) {
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
  }
  return notifications;
}

async function buildUserOutcomeNotifications(userId: string): Promise<BacklogNotificationDetail[]> {
  const [{ data: myPodOutcomes, error: myPodError }, { data: myReviewOutcomes, error: myReviewError }] =
    await fetchRecentUserOutcomes(userId);
  const notifications: BacklogNotificationDetail[] = [];
  if (!myPodError && Array.isArray(myPodOutcomes)) {
    for (const row of myPodOutcomes) {
      const payload = { eventType: "UPDATE", new: row, old: { status: "pending", user_id: userId } };
      notifications.push({
        eventType: "UPDATE",
        table: "pod_activation_requests",
        payload,
        message: getPodRequestMessage("UPDATE", payload),
        targetPath: getPodRequestTargetPath(payload, userId, null),
      });
    }
  }
  if (!myReviewError && Array.isArray(myReviewOutcomes)) {
    for (const row of myReviewOutcomes) {
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
  const requesterLabelCacheRef = useRef<Record<string, string>>({});
  const realtimeEnabled = process.env.NEXT_PUBLIC_ENABLE_GLOBAL_REALTIME !== "false";

  const persistNotification = useCallback(async (userId: string, detail: {
    eventType: "INSERT" | "UPDATE" | "DELETE";
    table: "pod_activation_requests" | "device_sync_logs" | "decision_reviews";
    message: string;
    targetPath?: string;
    fingerprint: string;
  }) => {
    const dedupeSince = new Date(Date.now() - 20_000).toISOString();
    const { data: existing } = await supabase
      .from("user_notifications")
      .select("id")
      .eq("user_id", userId)
      .eq("source_fingerprint", detail.fingerprint)
      .gte("created_at", dedupeSince)
      .limit(1);
    if (Array.isArray(existing) && existing.length > 0) return;

    await supabase
      .from("user_notifications")
      .insert({
        user_id: userId,
        table_name: detail.table,
        event_type: detail.eventType,
        message: detail.message,
        target_path: detail.targetPath ?? null,
        source_fingerprint: detail.fingerprint,
      });
  }, []);

  const cleanupChannels = useCallback(() => {
    for (const channel of channelsRef.current) {
      supabase.removeChannel(channel);
    }
    channelsRef.current = [];
  }, []);

  const resolveRequesterLabel = useCallback(async (userId: string | null | undefined): Promise<string> => {
    if (!userId) return "a user";
    const cached = requesterLabelCacheRef.current[userId];
    if (cached) return cached;
    const fallback = `user ${String(userId).slice(0, 8)}`;
    try {
      const { data, error } = await supabase
        .from("app_users")
        .select("full_name,email")
        .eq("user_id", userId)
        .maybeSingle();
      if (error) throw error;
      const fullName =
        typeof data?.full_name === "string" && data.full_name.trim().length > 0
          ? data.full_name.trim()
          : "";
      const email =
        typeof data?.email === "string" && data.email.trim().length > 0 ? data.email.trim() : "";
      const label = fullName || email || fallback;
      requesterLabelCacheRef.current[userId] = label;
      return label;
    } catch {
      requesterLabelCacheRef.current[userId] = fallback;
      return fallback;
    }
  }, []);

  const syncNotificationBacklog = useCallback(async (userId: string, role: string | null) => {
    if (typeof window === "undefined") return;
    const markerKey = `nb:notifications-backlog-synced:${userId}:${role ?? "none"}`;
    if (window.sessionStorage.getItem(markerKey) === "1") return;

    try {
      const backlogNotifications = isAdminRole(role)
        ? await buildAdminBacklogNotifications(userId, role, resolveRequesterLabel)
        : await buildUserOutcomeNotifications(userId);
      for (const notification of backlogNotifications) {
        pushRealtimeNotification(notification);
      }
    } finally {
      // Avoid duplicating backlog notifications on every refresh in the same session.
      window.sessionStorage.setItem(markerKey, "1");
    }
  }, [resolveRequesterLabel]);

  const startRealtimeForUser = useCallback(async (userId: string) => {
    if (currentUserIdRef.current === userId) return;

    cleanupChannels();
    currentUserIdRef.current = userId;
    try {
      const { data: roleRows, error } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", userId);
      if (error) throw error;

      const roles: string[] = Array.isArray(roleRows)
        ? roleRows.flatMap((row) => (row?.role ? [row.role] : []))
        : [];

      // Resolve deterministic role priority for notification routing.
      if (roles.includes("global_admin")) {
        currentRoleRef.current = "global_admin";
      } else if (roles.includes("admin")) {
        currentRoleRef.current = "admin";
      } else {
        currentRoleRef.current = roles[0] ?? null;
      }
    } catch {
      currentRoleRef.current = null;
    }

    // Notifications are now persisted in DB per user, so we avoid synthetic backlog replay.

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
          if (pushed && currentUserIdRef.current) {
            void persistNotification(currentUserIdRef.current, {
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
        safeLog.info("realtime_channel_status", {
          channel: "global-notifications-live",
          status,
          error: err?.message,
        });
      });

    channelsRef.current = [deviceChannel, notificationsChannel];
  }, [cleanupChannels, persistNotification, resolveRequesterLabel, toast]);

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
