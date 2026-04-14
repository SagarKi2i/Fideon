import { useCallback, useEffect, useState } from "react";
import {
  REALTIME_NOTIFICATION_STORE_UPDATED_EVENT,
} from "@/lib/realtimeNotificationStore";
import type { StoredRealtimeNotification } from "@/lib/realtimeNotificationStore";
import { supabase } from "@/integrations/supabase/client";

export function useRealtimeNotificationInbox() {
  const [items, setItems] = useState<StoredRealtimeNotification[]>([]);

  const refresh = useCallback(() => {
    void (async () => {
      const { data: userData } = await supabase.auth.getUser();
      const user = userData.user;
      if (!user) {
        setItems([]);
        return;
      }

      const { data, error } = await (supabase as any)
        .from("user_notifications")
        .select("id, table_name, event_type, message, target_path, created_at, read_at, source_fingerprint")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false })
        .limit(50);

      if (error) {
        setItems([]);
        return;
      }

      const mapped: StoredRealtimeNotification[] = (data || []).map((row: any) => ({
        id: row.id,
        table: row.table_name as StoredRealtimeNotification["table"],
        eventType: row.event_type as StoredRealtimeNotification["eventType"],
        message: row.message,
        targetPath: row.target_path ?? undefined,
        createdAt: row.created_at,
        read: Boolean(row.read_at),
        fingerprint: row.source_fingerprint,
      }));
      setItems(mapped);
    })();
  }, []);

  useEffect(() => {
    refresh();
    const onStoreUpdated = () => refresh();
    window.addEventListener(REALTIME_NOTIFICATION_STORE_UPDATED_EVENT, onStoreUpdated);
    return () => {
      window.removeEventListener(REALTIME_NOTIFICATION_STORE_UPDATED_EVENT, onStoreUpdated);
    };
  }, [refresh]);

  const unreadCount = items.filter((item: any) => !item.read).length;

  const markAllRead = useCallback(() => {
    void (async () => {
      const { data: userData } = await supabase.auth.getUser();
      const user = userData.user;
      if (!user) return;
      await (supabase as any)
        .from("user_notifications")
        .update({ read_at: new Date().toISOString() })
        .eq("user_id", user.id)
        .is("read_at", null);
      refresh();
    })();
  }, [refresh]);

  const clearAll = useCallback(() => {
    void (async () => {
      const { data: userData } = await supabase.auth.getUser();
      const user = userData.user;
      if (!user) return;
      await (supabase as any)
        .from("user_notifications")
        .delete()
        .eq("user_id", user.id);
      refresh();
    })();
  }, [refresh]);

  const markRead = useCallback((id: string) => {
    void (async () => {
      await (supabase as any)
        .from("user_notifications")
        .update({ read_at: new Date().toISOString() })
        .eq("id", id)
        .is("read_at", null);
      refresh();
    })();
  }, [refresh]);

  return {
    items,
    unreadCount,
    markAllRead,
    markRead,
    clearAll,
  };
}
