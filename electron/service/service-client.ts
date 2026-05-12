/**
 * Pure Node.js heartbeat runner — no Electron imports.
 * Reads credentials from C:\ProgramData\FideonOS\device-auth.json so the
 * Windows service (running as SYSTEM) and the Electron UI (user session)
 * share the same credential store.
 */
import fs from "node:fs";
import path from "node:path";

export const PROG_DATA_DIR = path.join("C:\\ProgramData", "FideonOS");
export const CREDS_FILE = path.join(PROG_DATA_DIR, "device-auth.json");
export const PIPE_PATH = "\\\\.\\pipe\\FideonOSService";

export type DeviceAuth = {
  device_id: string;
  device_jwt: string;
  registered_at: string;
};

export type ServiceStatus = {
  running: boolean;
  device_id: string | null;
  status: "online" | "error" | "idle";
  last_heartbeat: string | null;
  error?: string;
};

function apiBaseUrl(): string {
  const raw = process.env.ELECTRON_API_BASE_URL || "http://localhost:8000";
  return raw.replace(/\/+$/, "");
}

export function readCredentials(): DeviceAuth | null {
  try {
    const raw = fs.readFileSync(CREDS_FILE, "utf8");
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if (parsed?.device_id && parsed?.device_jwt) {
      return parsed as unknown as DeviceAuth;
    }
    return null;
  } catch {
    return null;
  }
}

export function writeCredentials(auth: DeviceAuth): void {
  fs.mkdirSync(PROG_DATA_DIR, { recursive: true });
  fs.writeFileSync(CREDS_FILE, JSON.stringify(auth, null, 2), { encoding: "utf8", mode: 0o600 });
}

export function deleteCredentials(): void {
  try {
    fs.unlinkSync(CREDS_FILE);
  } catch {
    // ignore
  }
}

export class ServiceHeartbeatClient {
  private _deviceId: string | null = null;
  private _deviceJwt: string | null = null;
  private _status: "online" | "error" | "idle" = "idle";
  private _lastHeartbeat: string | null = null;
  private _lastError: string | null = null;
  private _timer: ReturnType<typeof setInterval> | null = null;
  private _stopped = false;
  private _log: (msg: string) => void;
  private _heartbeatSeconds: number;

  constructor(opts: { log?: (msg: string) => void; heartbeatSeconds?: number } = {}) {
    this._log = opts.log ?? console.log;
    this._heartbeatSeconds = Math.max(10, opts.heartbeatSeconds ?? 60);
  }

  getStatus(): ServiceStatus {
    return {
      running: !this._stopped,
      device_id: this._deviceId,
      status: this._status,
      last_heartbeat: this._lastHeartbeat,
      error: this._lastError ?? undefined,
    };
  }

  reloadCredentials(): void {
    const creds = readCredentials();
    if (creds) {
      this._deviceId = creds.device_id;
      this._deviceJwt = creds.device_jwt;
      this._log(`[service] credentials reloaded device_id=${creds.device_id}`);
    } else {
      this._log(`[service] no credentials found at ${CREDS_FILE}`);
    }
  }

  start(): void {
    this._stopped = false;
    this.reloadCredentials();
    this._timer = setInterval(() => void this._tick(), this._heartbeatSeconds * 1000);
    this._log(`[service] heartbeat started interval=${this._heartbeatSeconds}s`);
  }

  stop(): void {
    this._stopped = true;
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    this._log(`[service] heartbeat stopped`);
  }

  private async _tick(): Promise<void> {
    if (this._stopped) return;
    if (!this._deviceJwt) {
      this.reloadCredentials();
      if (!this._deviceJwt) {
        this._status = "idle";
        this._lastError = "No device credentials";
        return;
      }
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30_000);
    try {
      const res = await fetch(`${apiBaseUrl()}/api/v1/devices/heartbeat`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${this._deviceJwt}` },
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (res.ok) {
        this._status = "online";
        this._lastHeartbeat = new Date().toISOString();
        this._lastError = null;
        this._log(`[service] heartbeat ok`);
      } else if (res.status === 401 || res.status === 403) {
        // JWT rejected — clear in-memory JWT; wait for Electron to supply new credentials
        this._log(`[service] heartbeat auth error ${res.status} — clearing in-memory JWT`);
        this._deviceJwt = null;
        this._status = "error";
        this._lastError = `Auth error: HTTP ${res.status}`;
      } else {
        this._status = "error";
        this._lastError = `HTTP ${res.status}`;
        this._log(`[service] heartbeat error: HTTP ${res.status}`);
      }
    } catch (err: unknown) {
      clearTimeout(timer);
      const msg = err instanceof Error ? err.message : String(err);
      this._status = "error";
      this._lastError = msg;
      this._log(`[service] heartbeat exception: ${msg}`);
    }
  }
}

export const serviceClient = new ServiceHeartbeatClient();
