import type { NotificationRealtimeDetail } from "@/lib/realtimeEvents";

export const REALTIME_NOTIFICATION_STORE_UPDATED_EVENT = "nb:notification-store-updated";

const STORAGE_KEY = "nb:realtime-notifications:v1";
const MAX_NOTIFICATIONS = 50;
const DEDUPE_WINDOW_MS = 20_000;

export type StoredRealtimeNotification = {
  id: string;
  table: NotificationRealtimeDetail["table"];
  eventType: NotificationRealtimeDetail["eventType"];
  message: string;
  createdAt: string;
  read: boolean;
  fingerprint: string;
};

function readStore(): StoredRealtimeNotification[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeStore(items: StoredRealtimeNotification[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_NOTIFICATIONS)));
  window.dispatchEvent(new CustomEvent(REALTIME_NOTIFICATION_STORE_UPDATED_EVENT));
}

function buildFingerprint(detail: NotificationRealtimeDetail): string {
  const payload = (detail.payload || {}) as {
    new?: { id?: string; status?: string };
    old?: { id?: string; status?: string };
  };
  const rowId = payload.new?.id || payload.old?.id || "unknown";
  const status = payload.new?.status || payload.old?.status || "na";
  return `${detail.table}:${detail.eventType}:${String(rowId)}:${String(status)}`;
}

export function getRealtimeNotifications(): StoredRealtimeNotification[] {
  return readStore();
}

export function pushRealtimeNotification(
  detail: NotificationRealtimeDetail,
): StoredRealtimeNotification | null {
  const current = readStore();
  const fingerprint = buildFingerprint(detail);
  const now = Date.now();

  const isDuplicate = current.some((item) => {
    if (item.fingerprint !== fingerprint) return false;
    const itemTs = new Date(item.createdAt).getTime();
    return Number.isFinite(itemTs) && now - itemTs < DEDUPE_WINDOW_MS;
  });

  if (isDuplicate) return null;

  const next: StoredRealtimeNotification = {
    id: `${now}-${Math.random().toString(36).slice(2, 10)}`,
    table: detail.table,
    eventType: detail.eventType,
    message: detail.message,
    createdAt: new Date(now).toISOString(),
    read: false,
    fingerprint,
  };

  writeStore([next, ...current]);
  return next;
}

export function markRealtimeNotificationsRead() {
  const current = readStore();
  writeStore(current.map((item) => ({ ...item, read: true })));
}

export function clearRealtimeNotifications() {
  writeStore([]);
}
