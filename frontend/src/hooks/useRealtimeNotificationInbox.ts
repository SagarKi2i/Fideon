import { useCallback, useEffect, useState } from "react";
import {
  clearRealtimeNotifications,
  getRealtimeNotifications,
  markRealtimeNotificationRead,
  markRealtimeNotificationsRead,
  REALTIME_NOTIFICATION_STORE_UPDATED_EVENT,
  type StoredRealtimeNotification,
} from "@/lib/realtimeNotificationStore";

export function useRealtimeNotificationInbox() {
  const [items, setItems] = useState<StoredRealtimeNotification[]>([]);

  const refresh = useCallback(() => {
    setItems(getRealtimeNotifications());
  }, []);

  useEffect(() => {
    refresh();
    const onStoreUpdated = () => refresh();
    window.addEventListener(REALTIME_NOTIFICATION_STORE_UPDATED_EVENT, onStoreUpdated);
    return () => {
      window.removeEventListener(REALTIME_NOTIFICATION_STORE_UPDATED_EVENT, onStoreUpdated);
    };
  }, [refresh]);

  const unreadCount = items.filter((item) => !item.read).length;

  const markAllRead = useCallback(() => {
    markRealtimeNotificationsRead();
    refresh();
  }, [refresh]);

  const clearAll = useCallback(() => {
    clearRealtimeNotifications();
    refresh();
  }, [refresh]);

  const markRead = useCallback((id: string) => {
    markRealtimeNotificationRead(id);
    refresh();
  }, [refresh]);

  return {
    items,
    unreadCount,
    markAllRead,
    markRead,
    clearAll,
  };
}
