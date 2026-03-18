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

export interface DeviceRegisterV1Response {
  success: boolean;
  device_token: string; // device JWT
  device_id: string;
  device_name: string;
  is_new: boolean;
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
  login_action_link?: string | null;
  login_email?: string | null;
  login_email_otp?: string | null;
  login_handoff_error?: string | null;
  device: {
    id: string;
    name: string;
    token: string;
  };
}

async function readErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") || "";
  try {
    if (contentType.includes("application/json")) {
      const data = await response.json();
      return data?.detail || data?.error || JSON.stringify(data);
    }
    const text = await response.text();
    // Some backends return plain text "Internal Server Error"
    return text || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export async function registerDeviceV1(payload: {
  hardware_fingerprint?: string;
  device_token?: string;
  device_name?: string;
  os_type?: string;
  app_version?: string;
  metadata?: Record<string, unknown>;
}): Promise<DeviceRegisterV1Response> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/devices/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return response.json();
}

export async function fetchDeviceModels(deviceJwt: string): Promise<DeviceModelsResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/devices/models`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${deviceJwt}`,
    },
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return response.json();
}

export async function performDeviceCheckin(
  deviceJwt: string,
  localModels: { model_id: string; is_downloaded: boolean }[]
): Promise<{ success: boolean; device_id: string; last_seen_at: string }> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/devices/heartbeat`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${deviceJwt}`,
    },
    body: JSON.stringify({ local_models: localModels }),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
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

export function getStoredDeviceJwt(): string | null {
  return localStorage.getItem("device_jwt");
}

export function setStoredDeviceJwt(jwt: string): void {
  localStorage.setItem("device_jwt", jwt);
}

export function clearStoredDeviceJwt(): void {
  localStorage.removeItem("device_jwt");
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
    throw new Error(await readErrorMessage(response));
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
    throw new Error(await readErrorMessage(response));
  }

  return response.json();
}

export async function confirmDevicePairing(payload: {
  pairing_id: string;
  pairing_code: string;
  auth_redirect_to?: string;
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
    throw new Error(await readErrorMessage(response));
  }

  return response.json();
}
