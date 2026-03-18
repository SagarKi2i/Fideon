export const REALTIME_DEVICE_EVENT = "nb:devices-changed";
export const REALTIME_NOTIFICATION_EVENT = "nb:notification";

export type DeviceRealtimeDetail = {
  eventType: "INSERT" | "UPDATE" | "DELETE";
  table: "devices";
  payload: unknown;
};

export type NotificationRealtimeDetail = {
  eventType: "INSERT" | "UPDATE" | "DELETE";
  table: "pod_activation_requests" | "device_sync_logs";
  payload: unknown;
  message: string;
};

export function emitDeviceRealtime(detail: DeviceRealtimeDetail) {
  window.dispatchEvent(new CustomEvent<DeviceRealtimeDetail>(REALTIME_DEVICE_EVENT, { detail }));
}

export function emitNotificationRealtime(detail: NotificationRealtimeDetail) {
  window.dispatchEvent(
    new CustomEvent<NotificationRealtimeDetail>(REALTIME_NOTIFICATION_EVENT, { detail }),
  );
}
