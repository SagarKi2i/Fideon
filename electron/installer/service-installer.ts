/**
 * Windows service registration helpers using node-windows.
 * Called from main.ts IPC handlers for install/uninstall.
 *
 * node-windows v1 is a CommonJS module with no bundled type declarations —
 * we load it with require() and provide a minimal inline interface.
 */
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const SERVICE_NAME = "FideonOS Device Service";
const SERVICE_DESC = "Keeps the FideonOS device heartbeat alive in the background, even when the UI is closed.";

// node-windows minimal interface (no @types package available)
interface NodeWindowsService {
  on(event: string, cb: (...args: unknown[]) => void): this;
  install(): void;
  uninstall(): void;
  start(): void;
  stop(): void;
  exists: boolean;
}

function makeService(scriptPath: string): NodeWindowsService {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { Service } = require("node-windows") as { Service: new (opts: Record<string, unknown>) => NodeWindowsService };
  return new Service({
    name: SERVICE_NAME,
    description: SERVICE_DESC,
    script: scriptPath,
    nodeOptions: [],
    env: [
      { name: "ELECTRON_API_BASE_URL", value: process.env.ELECTRON_API_BASE_URL || "http://localhost:8000" },
    ],
  });
}

function getServiceScript(resourcesPath: string | undefined, appPath: string): string {
  if (resourcesPath) {
    // Packaged build: service JS is bundled into resources/service/
    return path.join(resourcesPath, "service", "service-main.js");
  }
  // Dev: TypeScript compiled output
  return path.join(appPath, "dist", "service", "service-main.js");
}

export type ServiceInstallResult = { success: true } | { success: false; error: string };

export async function installService(opts: {
  resourcesPath?: string;
  appPath: string;
}): Promise<ServiceInstallResult> {
  return new Promise((resolve) => {
    try {
      const scriptPath = getServiceScript(opts.resourcesPath, opts.appPath);
      const svc = makeService(scriptPath);

      svc.on("install", () => {
        svc.start();
        resolve({ success: true });
      });
      svc.on("alreadyinstalled", () => {
        resolve({ success: true });
      });
      svc.on("error", (err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        resolve({ success: false, error: msg });
      });
      svc.on("invalidinstallation", () => {
        resolve({ success: false, error: "Invalid installation — run as Administrator" });
      });

      svc.install();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      resolve({ success: false, error: msg });
    }
  });
}

export async function uninstallService(opts: {
  resourcesPath?: string;
  appPath: string;
}): Promise<ServiceInstallResult> {
  return new Promise((resolve) => {
    try {
      const scriptPath = getServiceScript(opts.resourcesPath, opts.appPath);
      const svc = makeService(scriptPath);

      svc.on("uninstall", () => resolve({ success: true }));
      svc.on("alreadyuninstalled", () => resolve({ success: true }));
      svc.on("error", (err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        resolve({ success: false, error: msg });
      });

      svc.uninstall();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      resolve({ success: false, error: msg });
    }
  });
}

/** Returns true if the SCM service entry exists (regardless of running state). */
export async function isServiceInstalled(): Promise<boolean> {
  if (process.platform !== "win32") return false;
  try {
    await execFileAsync("sc", ["query", SERVICE_NAME]);
    return true;
  } catch {
    return false;
  }
}
