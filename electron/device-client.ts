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

function apiBaseUrl(): string {
  // In dev, backend runs at 8000 (frontend electron:dev starts it).
  const raw = process.env.ELECTRON_API_BASE_URL || "http://localhost:8000";
  return raw.replace(/\/+$/, "");
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

  // Validate stored JWT against the backend before trusting it
  if (existingJwt && existingId) {
    try {
      // Prefer heartbeat: validates JWT without adapter_registry domain setup.
      // 401/403 = invalid/expired/revoked JWT → re-register; otherwise token is accepted.
      const validateCtrl = new AbortController();
      const validateTimeout = setTimeout(() => validateCtrl.abort(), 30000);
      let res: Response;
      try {
        res = await fetch(`${apiBaseUrl()}/api/v1/devices/heartbeat`, {
          method: "PUT",
          headers: { Authorization: `Bearer ${existingJwt}` },
          signal: validateCtrl.signal,
        });
      } finally {
        clearTimeout(validateTimeout);
      }
      if (res.status !== 401 && res.status !== 403) {
        return { device_id: existingId, device_jwt: existingJwt };
      }
      opts?.log?.(`[device] stored JWT rejected by backend (${res.status}) — re-registering`);
    } catch {
      // Network error or timeout — use stored JWT so brief outages do not force re-register.
      return { device_id: existingId, device_jwt: existingJwt };
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
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);
  try {
    const res = await fetch(`${apiBaseUrl()}/api/v1/devices/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
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
    clearTimeout(timeoutId);
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      const p: any = payload;
      const msg = p?.error || p?.detail || JSON.stringify(payload) || `HTTP ${res.status}`;
      throw new Error(`Device register failed: ${msg}`);
    }
    return payload as { device_id: string; device_token: string };
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err?.name === "AbortError") {
      throw new Error(`Device registration timed out — backend unreachable at ${apiBaseUrl()}. Check your network or API URL.`);
    }
    throw err;
  }
}

class DeviceAuthError extends Error {
  status: number;
  constructor(msg: string, status: number) {
    super(msg);
    this.name = "DeviceAuthError";
    this.status = status;
  }
}

async function heartbeat(deviceJwt: string): Promise<void> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);
  try {
    const res = await fetch(`${apiBaseUrl()}/api/v1/devices/heartbeat`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${deviceJwt}` },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) {
      const payload = await res.json().catch(() => ({}));
      const p: any = payload;
      const msg = p?.error || p?.detail || JSON.stringify(payload) || `HTTP ${res.status}`;
      if (res.status === 401 || res.status === 403) {
        throw new DeviceAuthError(`Heartbeat failed: ${msg}`, res.status);
      }
      throw new Error(`Heartbeat failed: ${msg}`);
    }
  } catch (err: any) {
    clearTimeout(timeoutId);
    throw err;
  }
}

export function startHeartbeatLoop(
  deviceJwt: string,
  opts: {
    log: (msg: string) => void;
    heartbeatSeconds?: number;
    onDeactivated?: () => void;
  },
): { stop: () => void } {
  const hbSeconds = Math.max(10, Math.floor(opts.heartbeatSeconds ?? 60));
  let stopped = false;
  let timer: NodeJS.Timeout | null = null;

  const tick = async () => {
    if (stopped) return;
    try {
      await heartbeat(deviceJwt);
      opts.log(`[device] heartbeat ok`);
    } catch (e) {
      if (e instanceof DeviceAuthError) {
        // Guard: if stop() was called between when this tick started and now,
        // don't treat the 401 as admin-deactivation — the loop was intentionally stopped.
        if (stopped) return;
        opts.log(`[device] heartbeat auth error (${e.status}) — device deactivated by admin`);
        stopped = true;
        if (timer) clearInterval(timer);
        await clearStoredDeviceJwtAsync().catch(() => {});
        opts.onDeactivated?.();
        return;
      }
      opts.log(`[device] heartbeat error: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  // Do NOT run an immediate tick. ensureDeviceAuthAsync already validated (or freshly
  // issued) the JWT right before this is called. An instant heartbeat on a brand-new JWT
  // can hit the backend's propagation window and be misread as admin deactivation.
  timer = setInterval(() => void tick(), hbSeconds * 1000);

  return {
    stop: () => {
      stopped = true;
      if (timer) clearInterval(timer);
    },
  };
}

export async function ensureDeviceAuthAndStartHeartbeat(opts: {
  log: (msg: string) => void;
  heartbeatSeconds?: number;
  onDeactivated?: () => void;
}): Promise<{ stop: () => void }> {
  try {
    // Validate (or freshly register) before starting the loop. ensureDeviceAuthAsync
    // sends a heartbeat to confirm the stored JWT is still valid, and re-registers if
    // it gets 401/403. This prevents a stale post-logout JWT from being mistaken for
    // admin deactivation.
    opts.log(`[device] validating device auth... base=${apiBaseUrl()}`);
    const auth = await ensureDeviceAuthAsync({ log: opts.log });
    opts.log(`[device] device auth ready device_id=${auth.device_id}`);
    return startHeartbeatLoop(auth.device_jwt, opts);
  } catch (e) {
    opts.log(`[device] startup auth failed: ${e instanceof Error ? e.message : String(e)}`);
    return { stop: () => {} };
  }
}

