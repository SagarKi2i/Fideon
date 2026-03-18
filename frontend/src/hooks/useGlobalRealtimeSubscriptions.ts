import { useCallback, useEffect, useRef } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { emitDeviceRealtime, emitNotificationRealtime } from "@/lib/realtimeEvents";
import { safeLog } from "@/logger";
import { pushRealtimeNotification } from "@/lib/realtimeNotificationStore";

function getPodRequestMessage(eventType: string, payload: any): string {
  if (eventType === "INSERT") return "New pod activation request submitted.";
  const status = payload?.new?.status;
  if (status === "approved") return "A pod activation request was approved.";
  if (status === "rejected") return "A pod activation request was rejected.";
  return "A pod activation request was updated.";
}

function shouldEmitPodRequestEvent(payload: any): boolean {
  if (payload.eventType === "INSERT") return true;
  if (payload.eventType !== "UPDATE") return false;
  const prevStatus = payload.old?.status;
  const nextStatus = payload.new?.status;
  if (prevStatus === nextStatus) return false;
  return nextStatus === "approved" || nextStatus === "rejected";
}

export function useGlobalRealtimeSubscriptions() {
  const { toast } = useToast();
  const channelsRef = useRef<RealtimeChannel[]>([]);
  const currentUserIdRef = useRef<string | null>(null);
  const realtimeEnabled = process.env.NEXT_PUBLIC_ENABLE_GLOBAL_REALTIME !== "false";

  const cleanupChannels = useCallback(() => {
    for (const channel of channelsRef.current) {
      supabase.removeChannel(channel);
    }
    channelsRef.current = [];
  }, []);

  const startRealtimeForUser = useCallback((userId: string) => {
    if (currentUserIdRef.current === userId) return;

    cleanupChannels();
    currentUserIdRef.current = userId;

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
          if (!shouldEmitPodRequestEvent(payload)) return;
          const message = getPodRequestMessage(payload.eventType, payload);
          const detail = {
            eventType: payload.eventType,
            table: "pod_activation_requests" as const,
            payload,
            message,
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
        startRealtimeForUser(session.user.id);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (!active) return;
      if (event === "SIGNED_IN" && session?.user?.id) {
        startRealtimeForUser(session.user.id);
      } else if (event === "SIGNED_OUT") {
        cleanupChannels();
        currentUserIdRef.current = null;
      }
    });

    return () => {
      active = false;
      subscription.unsubscribe();
      cleanupChannels();
      currentUserIdRef.current = null;
    };
  }, [cleanupChannels, realtimeEnabled, startRealtimeForUser]);
}
