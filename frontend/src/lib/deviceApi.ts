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
