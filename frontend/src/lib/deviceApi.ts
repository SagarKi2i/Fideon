// Device API for Electron app integration
import { getApiBaseUrl } from "@/lib/apiBaseUrl";

export interface DeviceModel {
  model_id: string;
  model_name: string;
  domain: string;
  ollama_model_name: string;
  is_downloaded: boolean;
  allocated_at: string;
}

export interface DeviceModelsResponse {
  success: boolean;
  device_id: string;
  models: DeviceModel[];
  total_models: number;
}

export interface DevicePairingStartRequest {
  frontend_base_url?: string;
  expires_in_seconds?: number;
  primary_device_label?: string;
  requested_device_profile?: Record<string, unknown>;
}

export interface DevicePairingStartResponse {
  success: boolean;
  pairing_id: string;
  pairing_code: string;
  pairing_url: string;
  expires_at: string;
  status: "pending" | "confirmed" | "expired" | "cancelled";
}

export interface DevicePairingStatusResponse {
  success: boolean;
  pairing: {
    id: string;
    status: "pending" | "confirmed" | "expired" | "cancelled";
    expires_at: string;
    consumed_at: string | null;
    linked_device_id: string | null;
    created_at: string;
    confirmed_device_profile?: Record<string, unknown>;
  };
}

export interface DevicePairingConfirmResponse {
  success: boolean;
  pairing_id: string;
  status: "confirmed";
  device: {
    id: string;
    name: string;
    token: string;
  };
}

export async function fetchDeviceModels(deviceToken: string): Promise<DeviceModelsResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/device-models`, {
    method: 'GET',
    headers: {
      'x-device-token': deviceToken,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to fetch device models');
  }

  return response.json();
}

export async function performDeviceCheckin(
  deviceToken: string,
  localModels: { model_id: string; is_downloaded: boolean }[]
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${getApiBaseUrl()}/api/device-checkin`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-device-token': deviceToken,
    },
    body: JSON.stringify({
      os_type: navigator.platform,
      app_version: '1.0.0',
      local_models: localModels,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to perform check-in');
  }

  return response.json();
}

export function getStoredDeviceToken(): string | null {
  return localStorage.getItem('device_token');
}

export function setStoredDeviceToken(token: string): void {
  localStorage.setItem('device_token', token);
}

export function clearStoredDeviceToken(): void {
  localStorage.removeItem('device_token');
}

export async function startDevicePairing(
  accessToken: string,
  payload: DevicePairingStartRequest
): Promise<DevicePairingStartResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/devices/pairing/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "Failed to create pairing QR");
  }

  return response.json();
}

export async function getDevicePairingStatus(
  accessToken: string,
  pairingId: string
): Promise<DevicePairingStatusResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/devices/pairing/status/${encodeURIComponent(pairingId)}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "Failed to fetch pairing status");
  }

  return response.json();
}

export async function confirmDevicePairing(payload: {
  pairing_id: string;
  pairing_code: string;
  device_name?: string;
  os_type?: string;
  app_version?: string;
  confirmed_device_profile?: Record<string, unknown>;
}): Promise<DevicePairingConfirmResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/devices/pairing/confirm`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "Failed to confirm pairing");
  }

  return response.json();
}
