import { useCallback, useEffect, useState } from "react";
import {
  REALTIME_NOTIFICATION_STORE_UPDATED_EVENT,
} from "@/lib/realtimeNotificationStore";
import type { StoredRealtimeNotification } from "@/lib/realtimeNotificationStore";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";

async function getToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = await getToken();
  return fetch(apiUrl(path), {
    ...options,
    headers: {
      ...(options.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
    },
  });
}

export function useRealtimeNotificationInbox() {
  const [items, setItems] = useState<StoredRealtimeNotification[]>([]);

  const refresh = useCallback(() => {
    void (async () => {
      const token = await getToken();
      if (!token) {
        setItems([]);
        return;
      }

      try {
        const res = await apiFetch("/api/v1/notifications");
        if (!res.ok) {
          setItems([]);
          return;
        }
        const payload = await res.json();
        const rows: any[] = payload.notifications ?? [];

        const mapped: StoredRealtimeNotification[] = rows.map((row: any) => ({
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
      } catch {
        setItems([]);
      }
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
      await apiFetch("/api/v1/notifications/mark-all-read", { method: "POST" });
      refresh();
    })();
  }, [refresh]);

  const clearAll = useCallback(() => {
    void (async () => {
      await apiFetch("/api/v1/notifications", { method: "DELETE" });
      refresh();
    })();
  }, [refresh]);

  const markRead = useCallback((id: string) => {
    void (async () => {
      await apiFetch(`/api/v1/notifications/${encodeURIComponent(id)}/mark-read`, { method: "PATCH" });
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
