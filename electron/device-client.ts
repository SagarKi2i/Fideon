import os from "node:os";
import { machineIdSync } from "node-machine-id";

type StoredDeviceAuth = {
  device_id?: string;
  device_jwt?: string;
  registered_at?: string;
};

export function getMachineName(): string {
  return os.hostname() || "Edge Device";
}

// Stable per-machine ID (not MAC-based). Treat as sensitive.
export function getMachineId(): string {
  return machineIdSync(true);
}

// electron-store v11 is ESM-only. Our Electron main process is compiled to CommonJS,
// so we must load it via dynamic import() to avoid ERR_REQUIRE_ESM at runtime.
// Note: TypeScript rewrites `import("x")` to `require("x")` under `module: commonjs`,
// so use a runtime dynamic import via Function to preserve ESM loading.
const _dynamicImport = new Function("specifier", "return import(specifier)") as (specifier: string) => Promise<any>;
let storePromise: Promise<any> | null = null;
async function getStore(): Promise<any> {
  if (!storePromise) {
    storePromise = _dynamicImport("electron-store").then((m: any) => {
      const StoreCtor = m?.default ?? m;
      // StoreCtor is `any` here (dynamic ESM import), so avoid type arguments.
      return new StoreCtor({ name: "device-auth" }) as any as {
        get?: (key: keyof StoredDeviceAuth | string) => unknown;
        set?: (key: keyof StoredDeviceAuth | string, value: unknown) => void;
        delete?: (key: keyof StoredDeviceAuth | string) => void;
      };
    });
  }
  return storePromise;
}

/**
 * Base URL for device register/heartbeat from the Electron **main** process.
 * Must match `NEXT_PUBLIC_API_URL` / `frontend` `getApiBaseUrl()` for local dev (default 8080).
 * Override with `ELECTRON_API_BASE_URL` or `electron/.env` (packaged: `resources/.env`).
 */
export const DEFAULT_ELECTRON_API_BASE_URL = "http://127.0.0.1:8080";

export function getElectronApiBaseUrl(): string {
  const raw = process.env.ELECTRON_API_BASE_URL || DEFAULT_ELECTRON_API_BASE_URL;
  return raw.replace(/\/+$/, "");
}

function apiBaseUrl(): string {
  return getElectronApiBaseUrl();
}

function deviceLabel(): string {
  const hostname = getMachineName();
  const platform = process.platform;
  return `${hostname} (${platform})`;
}

export function getStoredDeviceJwt(): string | undefined {
  // Kept for backward compatibility, but can't be sync with dynamic import.
  // Prefer `getStoredDeviceJwtAsync`.
  return undefined;
}

export function clearStoredDeviceJwt(): void {
  // Kept for backward compatibility, but can't be sync with dynamic import.
}

export async function getStoredDeviceJwtAsync(): Promise<string | undefined> {
  const store = await getStore();
  const jwt = store.get?.("device_jwt");
  return jwt ? String(jwt) : undefined;
}

export async function clearStoredDeviceJwtAsync(): Promise<void> {
  const store = await getStore();
  store.delete?.("device_jwt");
  store.delete?.("device_id");
  store.delete?.("registered_at");
}

export async function getStoredDeviceIdAsync(): Promise<string | undefined> {
  const store = await getStore();
  const deviceId = store.get?.("device_id");
  return deviceId ? String(deviceId) : undefined;
}

export async function ensureDeviceAuthAsync(opts?: { log?: (msg: string) => void }): Promise<{ device_id: string; device_jwt: string }> {
  const store = await getStore();
  const existingJwt = await getStoredDeviceJwtAsync();
  const existingId = await getStoredDeviceIdAsync();
  if (existingJwt && existingId) {
    try {
      await heartbeat(existingJwt);
      return { device_id: existingId, device_jwt: existingJwt };
    } catch (e) {
      const status =
        e && typeof e === "object" && "httpStatus" in e ? (e as { httpStatus?: number }).httpStatus : undefined;
      if (status === 401 || status === 403) {
        opts?.log?.(
          `[device] stored JWT rejected (${status}), clearing and re-registering... base=${apiBaseUrl()}`,
        );
        store.delete?.("device_jwt");
        store.delete?.("device_id");
        store.delete?.("registered_at");
      } else {
        throw e;
      }
    }
  }

  opts?.log?.(`[device] ensureDeviceAuthAsync registering... base=${apiBaseUrl()}`);
  const reg = await registerDevice();
  store.set?.("device_id", reg.device_id);
  store.set?.("device_jwt", reg.device_token);
  store.set?.("registered_at", new Date().toISOString());
  return { device_id: reg.device_id, device_jwt: reg.device_token };
}

async function registerDevice(): Promise<{ device_id: string; device_token: string }> {
  const hw = getMachineId();
  const res = await fetch(`${apiBaseUrl()}/api/v1/devices/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      hardware_fingerprint: hw,
      device_name: deviceLabel(),
      os_type: process.platform,
      app_version: process.env.npm_package_version || undefined,
      metadata: {
        source: "electron-main",
      },
    }),
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    const p: any = payload;
    const msg = p?.error || p?.detail || JSON.stringify(payload) || `HTTP ${res.status}`;
    throw new Error(`Device register failed: ${msg}`);
  }
  return payload as { device_id: string; device_token: string };
}

async function heartbeat(deviceJwt: string): Promise<void> {
  const res = await fetch(`${apiBaseUrl()}/api/v1/devices/heartbeat`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${deviceJwt}`,
    },
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    const p: any = payload;
    const msg = p?.error || p?.detail || JSON.stringify(payload) || `HTTP ${res.status}`;
    const err = new Error(`Heartbeat failed: ${msg}`) as Error & { httpStatus?: number };
    err.httpStatus = res.status;
    throw err;
  }
}

export async function ensureDeviceAuthAndStartHeartbeat(opts: {
  log: (msg: string) => void;
  heartbeatSeconds?: number;
}): Promise<{ stop: () => void }> {
  const store = await getStore();
  const hbSeconds = Math.max(10, Math.floor(opts.heartbeatSeconds ?? 60));
  let stopped = false;
  let timer: NodeJS.Timeout | null = null;

  const startLoop = (jwt: string) => {
    const tick = async () => {
      if (stopped) return;
      try {
        await heartbeat(jwt);
        opts.log(`[device] heartbeat ok`);
      } catch (e) {
        opts.log(`[device] heartbeat error: ${e instanceof Error ? e.message : String(e)}`);
      }
    };
    // Run an initial beat quickly, then every hbSeconds.
    void tick();
    timer = setInterval(() => void tick(), hbSeconds * 1000);
  };

  try {
    const existing = await getStoredDeviceJwtAsync();
    if (existing) {
      opts.log(`[device] using stored device JWT`);
      startLoop(existing);
      return { stop: () => (stopped = true, timer && clearInterval(timer)) };
    }

    opts.log(`[device] registering device... base=${apiBaseUrl()}`);
    const reg = await ensureDeviceAuthAsync({ log: opts.log });
    opts.log(`[device] registered device_id=${reg.device_id}`);
    startLoop(reg.device_jwt);
  } catch (e) {
    opts.log(`[device] registration failed: ${e instanceof Error ? e.message : String(e)}`);
  }

  return {
    stop: () => {
      stopped = true;
      if (timer) clearInterval(timer);
    },
  };
}

