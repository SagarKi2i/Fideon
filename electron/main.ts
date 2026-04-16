// Electron main process entrypoint.
// Creates the BrowserWindow and wires IPC handlers that call into
// the local Ollama backend helpers.
import "dotenv/config";

import { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, protocol, session } from "electron";
import fs from "node:fs";
import path from "path";
import {
  runOllamaCheckStatus,
  runListModels,
  runPullModel,
  runGenerate,
  runDeleteModel,
} from "./ollama-backend";
import { createHandler } from "next-electron-rsc";
import {
  ensureDeviceAuthAndStartHeartbeat,
  ensureDeviceAuthAsync,
  getStoredDeviceIdAsync,
  getStoredDeviceJwtAsync,
  getMachineId,
  getMachineName,
  clearStoredDeviceJwtAsync,
} from "./device-client";
import { checkForModelUpdate, downloadAndInstall } from "./model-updater";

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;
let deviceHeartbeatStopper: (() => void) | null = null;

function electronApiBase(): string {
  const raw = process.env.ELECTRON_API_BASE_URL?.replace(/\/+$/, "") ?? "http://localhost:8000";
  return raw.replace(/\/+$/, "");
}

async function readJsonSafe(res: Response): Promise<any> {
  try {
    return await res.json();
  } catch {
    return {};
  }
}

async function callBackendApi(opts: {
  path: string;
  method: "GET" | "POST" | "PATCH" | "DELETE";
  accessToken: string;
  body?: any;
}): Promise<{ ok: true; status: number; payload: any } | { ok: false; status: number; payload: any }> {
  const url = `${electronApiBase()}${opts.path.startsWith("/") ? "" : "/"}${opts.path}`;
  const res = await fetch(url, {
    method: opts.method,
    headers: {
      Authorization: `Bearer ${opts.accessToken}`,
      "Content-Type": "application/json",
    },
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  });
  const payload = await readJsonSafe(res);
  if (res.ok) return { ok: true, status: res.status, payload };
  return { ok: false, status: res.status, payload };
}

const logPath = path.join(app.getPath("userData"), "fideon-main.log");
function log(msg: string) {
  try {
    fs.appendFileSync(logPath, `${new Date().toISOString()} ${msg}\n`, "utf8");
  } catch {
    // ignore logging failures
  }
}

function formatUnknownError(err: unknown): string {
  if (err instanceof Error) return `${err.message}\n${err.stack}`;
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err, null, 2);
  } catch {
    return String(err);
  }
}

async function waitForHttpReady(
  url: string,
  opts?: { timeoutMs?: number; perAttemptTimeoutMs?: number; minDelayMs?: number; maxDelayMs?: number },
): Promise<{ ok: true; status?: number } | { ok: false; reason: string }> {
  const timeoutMs = opts?.timeoutMs ?? 60_000;
  const perAttemptTimeoutMs = opts?.perAttemptTimeoutMs ?? 2_500;
  const minDelayMs = opts?.minDelayMs ?? 250;
  const maxDelayMs = opts?.maxDelayMs ?? 2_000;

  const startedAt = Date.now();
  let attempt = 0;
  let delayMs = minDelayMs;

  while (Date.now() - startedAt < timeoutMs) {
    attempt += 1;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), perAttemptTimeoutMs);
    try {
      const res = await fetch(url, {
        method: "GET",
        signal: controller.signal,
        // Avoid any caching/proxy weirdness in dev.
        headers: { "cache-control": "no-cache" },
      });
      clearTimeout(timer);
      return { ok: true, status: res.status };
    } catch (err) {
      clearTimeout(timer);
      const elapsed = Date.now() - startedAt;
      log(
        `[main] waitForHttpReady attempt=${attempt} elapsedMs=${elapsed} url=${url} err=${formatUnknownError(err)}`,
      );
      await new Promise((r) => setTimeout(r, delayMs));
      delayMs = Math.min(maxDelayMs, Math.floor(delayMs * 1.4));
    }
  }

  return { ok: false, reason: `Timed out waiting for ${url} after ${timeoutMs}ms` };
}

// Only treat *packaged* builds as production.
// Local `npm start` should always behave as dev even if NODE_ENV is set.
const isProd = app.isPackaged;
const isDev = !app.isPackaged;

function ensureRequiredServerFilesJson(nextProjectDir: string) {
  // next-electron-rsc requires `.next/required-server-files.json` to exist.
  const nextDir = path.join(nextProjectDir, ".next");
  const required = path.join(nextDir, "required-server-files.json");
  try {
    if (fs.existsSync(required)) return;
    fs.mkdirSync(nextDir, { recursive: true });
    fs.writeFileSync(
      required,
      JSON.stringify(
        {
          version: 1,
          config: { distDir: ".next", output: "standalone" },
        },
        null,
        2,
      ),
      "utf8",
    );
  } catch (err) {
    // Best-effort: missing file will surface as a clearer runtime error.
    console.error("[main] Failed to ensure required-server-files.json:", err);
  }
}

// Initialize next-electron-rsc only for production/packaged runs.
// In dev, we load the real Next.js dev server, and do not intercept.
let nextRsc: ReturnType<typeof createHandler> | null = null;
if (isProd) {
  // next-electron-rsc calls protocol.registerSchemesAsPrivileged which must run
  // before app is ready, so it must be initialized at module load time.
  // In packaged builds, Next's standalone output is bundled into the app root.
  const nextDirForProd = app.getAppPath();
  ensureRequiredServerFilesJson(nextDirForProd);
  nextRsc = createHandler({
    protocol,
    dir: nextDirForProd,
    dev: false,
    hostname: "localhost",
    port: 3000,
  });
}

// Ensure a single running instance; focus existing window on second launch.
const gotLock = app.requestSingleInstanceLock();

if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// Log unexpected main-process errors for easier debugging.
process.on("uncaughtException", (err) => {
  console.error("[main] Uncaught exception:", err);
  log(`[main] uncaughtException: ${formatUnknownError(err)}`);
});

process.on("unhandledRejection", (reason) => {
  console.error("[main] Unhandled rejection:", reason);
  log(`[main] unhandledRejection: ${formatUnknownError(reason)}`);
});

function createTray() {
  if (tray) return;

  // Important: in packaged apps, dev-only relative paths to `frontend/src/assets/...`
  // won't exist. Prefer an icon that we copy into Electron `resources/`.
  const iconCandidates = [
    path.join(process.resourcesPath, "fideon-tray.png"),
    path.join(process.resourcesPath, "icon-256.png"),
    path.join(app.getAppPath(), "fideon-tray.png"),
    path.join(app.getAppPath(), "icon-256.png"),
    // Dev fallback (when running locally)
    path.join(
      __dirname,
      "..",
      "..",
      "frontend",
      "src",
      "assets",
      "fideon-logo.png",
    ),
  ];

  const iconPath = iconCandidates.find((p) => fs.existsSync(p)) ?? iconCandidates[0];
  log(`[main] tray iconPath=${iconPath} exists=${fs.existsSync(iconPath)}`);

  // nativeImage.createFromPath("") yields an empty image; if the file is missing we
  // still create a tray object to avoid total startup failure.
  let icon = nativeImage.createFromPath(iconPath);
  if (icon.isEmpty()) icon = nativeImage.createEmpty();
  log(`[main] tray icon empty=${icon.isEmpty()}`);

  tray = new Tray(icon);
  log(`[main] tray created`);
  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Show Fideon OS",
      click: () => {
        if (!mainWindow) return;
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.show();
        mainWindow.focus();
      },
    },
    {
      label: "Quit",
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setToolTip("Fideon OS");
  tray.setContextMenu(contextMenu);
  tray.on("click", () => {
    if (!mainWindow) return;
    if (!mainWindow.isVisible()) {
      mainWindow.show();
    }
    mainWindow.focus();
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Ensure the window is visible (some systems can initially start hidden).
  mainWindow.once("ready-to-show", () => {
    if (!mainWindow) return;
    mainWindow.show();
    mainWindow.focus();
    log(`[main] ready-to-show -> show+focus`);
  });

  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription) => {
    // eslint-disable-next-line no-console
    console.error("[main] did-fail-load:", { errorCode, errorDescription });
    log(`[main] did-fail-load: ${errorCode} ${String(errorDescription)}`);
  });

  // In dev, point to Next.js dev server; in prod, load the same URL
  // which is intercepted by next-electron-rsc (no open port).
  const startUrl =
    // Default to the main frontend page (not the ElectronPlayground demo page).
    process.env.ELECTRON_START_URL ?? "http://localhost:3000/";
  log(`[main] loading startUrl=${startUrl}`);

  try {
    if (isDev) {
      // Hitting `/` on a Next dev server can block for a long time on the very first
      // compile ("Compiling / ..."). Probe a fast static asset instead so Electron
      // can reliably detect readiness.
      let probeUrl = startUrl;
      try {
        const u = new URL(startUrl);
        u.pathname = "/favicon.ico";
        u.search = "";
        u.hash = "";
        probeUrl = u.toString();
      } catch {
        // If startUrl isn't a valid URL, fall back to probing the original.
        probeUrl = startUrl;
      }

      const ready = await waitForHttpReady(probeUrl, {
        timeoutMs: 120_000,
        perAttemptTimeoutMs: 10_000,
      });
      if (!ready.ok) {
        const html = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Fideon OS — Dev server not ready</title>
    <style>
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 24px; }
      code { background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }
      .box { border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; max-width: 860px; }
      h1 { margin: 0 0 8px; font-size: 18px; }
      p { margin: 8px 0; line-height: 1.4; }
      .muted { color: #6b7280; font-size: 12px; }
    </style>
  </head>
  <body>
    <div class="box">
      <h1>Frontend dev server not reachable</h1>
      <p>Electron is trying to load <code>${startUrl}</code> but it never responded.</p>
      <p class="muted">Probe URL: <code>${probeUrl}</code></p>
      <p>Start the frontend first (from <code>frontend/</code>): <code>npm run dev</code> or <code>npm run electron:dev</code>.</p>
      <p class="muted">${ready.reason}</p>
    </div>
  </body>
</html>`;
        await mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
        return;
      }
      log(`[main] dev startUrl reachable status=${String((ready as any).status)}`);
    }

    await mainWindow.loadURL(startUrl);
    // Ensure the window is visible when Next finishes wiring up.
    mainWindow.show();
    mainWindow.focus();
    log(`[main] loadURL success`);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("[main] loadURL failed:", err);
    log(`[main] loadURL failed: ${String(err)}`);
  }

  mainWindow.webContents.once("dom-ready", () => {
    if (!mainWindow) return;
    mainWindow.show();
    mainWindow.focus();
  });
  createTray();
}

app.whenReady().then(async () => {
  if (isProd && nextRsc) {
    // Production: intercept localhostUrl and serve Next internally (no open port).
    await nextRsc.createInterceptor({ session: session.defaultSession });
  }

  try {
    const runner = await ensureDeviceAuthAndStartHeartbeat({ log, heartbeatSeconds: 60 });
    deviceHeartbeatStopper = runner.stop;
  } catch (err) {
    log(`[device] ensureDeviceAuthAndStartHeartbeat failed: ${formatUnknownError(err)}`);
  }

  await createWindow();
});

app.on("before-quit", () => {
  try {
    deviceHeartbeatStopper?.();
  } catch {
    // ignore
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    void createWindow();
  } else if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
  }
});

// IPC: Ollama status and model management
ipcMain.handle("ollama:checkStatus", async () => runOllamaCheckStatus());

ipcMain.handle("ollama:listModels", async () => runListModels());

ipcMain.handle("ollama:pullModel", async (event, modelName: string) =>
  runPullModel(modelName, (progress) =>
    event.sender.send("ollama:pullProgress", progress),
  ),
);

ipcMain.handle(
  "ollama:generate",
  async (event, params: { model: string; prompt: string; system?: string }) =>
    runGenerate(params, (chunk) =>
      event.sender.send("ollama:generateChunk", chunk),
    ),
);

ipcMain.handle("ollama:deleteModel", async (_event, modelName: string) =>
  runDeleteModel(modelName),
);

// IPC: simple network status placeholder
ipcMain.handle("network:checkStatus", async () => ({ online: true }));

// IPC: device info for manual linking (Pattern 2)
ipcMain.handle("device:getDeviceId", async () => {
  try {
    const id = await getStoredDeviceIdAsync();
    return { success: true, device_id: id ?? null };
  } catch (err) {
    return { success: false, error: String(err) };
  }
});

ipcMain.handle("device:getAuth", async () => {
  try {
    const [id, jwt] = await Promise.all([getStoredDeviceIdAsync(), getStoredDeviceJwtAsync()]);
    return { success: true, device_id: id ?? null, device_jwt: jwt ?? null };
  } catch (err) {
    return { success: false, error: String(err) };
  }
});

ipcMain.handle("device:clearAuth", async () => {
  try {
    try {
      deviceHeartbeatStopper?.();
    } catch {
      // ignore
    } finally {
      deviceHeartbeatStopper = null;
    }
    await clearStoredDeviceJwtAsync();
    return { success: true };
  } catch (err) {
    return { success: false, error: String(err) };
  }
});

ipcMain.handle("device:ensureAuth", async () => {
  try {
    log(`[ipc] device:ensureAuth called`);
    const auth = await ensureDeviceAuthAsync({ log });
    log(`[ipc] device:ensureAuth success device_id=${String(auth.device_id || "")}`);
    // Ensure heartbeat loop is running after an explicit reconnect.
    try {
      const runner = await ensureDeviceAuthAndStartHeartbeat({ log, heartbeatSeconds: 60 });
      deviceHeartbeatStopper = runner.stop;
    } catch (err) {
      log(`[device] ensureDeviceAuthAndStartHeartbeat failed: ${formatUnknownError(err)}`);
    }
    return { success: true, device_id: auth.device_id, device_jwt: auth.device_jwt };
  } catch (err) {
    log(`[ipc] device:ensureAuth failed: ${formatUnknownError(err)}`);
    return { success: false, error: formatUnknownError(err) };
  }
});

ipcMain.handle("device:getDeviceInfo", async () => {
  try {
    return {
      success: true,
      machineName: getMachineName(),
      machineId: getMachineId(),
      platform: process.platform,
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
});

// IPC: outbound webhooks management (calls backend with the user's Supabase access token)
ipcMain.handle("webhooks:list", async (_event, accessToken: string) => {
  try {
    const r = await callBackendApi({ path: "/api/v1/webhooks", method: "GET", accessToken });
    if (!r.ok) return { success: false, status: r.status, payload: r.payload };
    return { success: true, webhooks: r.payload?.webhooks ?? [] };
  } catch (err) {
    return { success: false, error: String(err) };
  }
});

ipcMain.handle(
  "webhooks:create",
  async (_event, accessToken: string, input: { url: string; description?: string; events?: string[] }) => {
    try {
      const r = await callBackendApi({
        path: "/api/v1/webhooks",
        method: "POST",
        accessToken,
        body: { url: input.url, description: input.description ?? "", events: input.events ?? [] },
      });
      if (!r.ok) return { success: false, status: r.status, payload: r.payload };
      return { success: true, ...r.payload };
    } catch (err) {
      return { success: false, error: String(err) };
    }
  },
);

ipcMain.handle(
  "webhooks:update",
  async (
    _event,
    accessToken: string,
    id: string,
    patch: Partial<{ url: string; description: string; events: string[]; is_active: boolean }>,
  ) => {
    try {
      const r = await callBackendApi({
        path: `/api/v1/webhooks/${encodeURIComponent(id)}`,
        method: "PATCH",
        accessToken,
        body: patch,
      });
      if (!r.ok) return { success: false, status: r.status, payload: r.payload };
      return { success: true };
    } catch (err) {
      return { success: false, error: String(err) };
    }
  },
);

ipcMain.handle("webhooks:delete", async (_event, accessToken: string, id: string) => {
  try {
    const r = await callBackendApi({
      path: `/api/v1/webhooks/${encodeURIComponent(id)}`,
      method: "DELETE",
      accessToken,
    });
    if (!r.ok) return { success: false, status: r.status, payload: r.payload };
    return { success: true };
  } catch (err) {
    return { success: false, error: String(err) };
  }
});

ipcMain.handle("webhooks:rotateSecret", async (_event, accessToken: string, id: string) => {
  try {
    const r = await callBackendApi({
      path: `/api/v1/webhooks/${encodeURIComponent(id)}/rotate-secret`,
      method: "POST",
      accessToken,
    });
    if (!r.ok) return { success: false, status: r.status, payload: r.payload };
    return { success: true, ...r.payload };
  } catch (err) {
    return { success: false, error: String(err) };
  }
});

// IPC: auto-launch placeholder using OS login items (where supported)
ipcMain.handle("settings:getAutoLaunch", async () => {
  try {
    if (process.platform === "darwin" || process.platform === "win32") {
      const settings = app.getLoginItemSettings();
      return { success: true, enabled: settings.openAtLogin };
    }
    return { success: true, enabled: false };
  } catch (error) {
    return { success: false, error: String(error) };
  }
});

ipcMain.handle("settings:setAutoLaunch", async (_event, enabled: boolean) => {
  try {
    if (process.platform === "darwin" || process.platform === "win32") {
      app.setLoginItemSettings({
        openAtLogin: enabled,
        openAsHidden: true,
      });
      return { success: true };
    }
    return { success: true }; // no-op on other platforms
  } catch (error) {
    return { success: false, error: String(error) };
  }
});

// IPC: model update check (canary-gated via backend)
ipcMain.handle("model:checkUpdate", async (_event, domain: string) => {
  try {
    const auth = await ensureDeviceAuthAsync({ log });
    const { device_id: deviceId, device_jwt: deviceJwt } = auth;
    const apiBase = electronApiBase();
    const result = await checkForModelUpdate({ domain, deviceId, deviceJwt, apiBase });
    return { success: true, ...result };
  } catch (err) {
    log(`[model] checkUpdate error: ${formatUnknownError(err)}`);
    return { success: false, error: String(err) };
  }
});

// IPC: download + SHA-256 verify + GPG verify + ollama create
ipcMain.handle(
  "model:downloadAndInstall",
  async (
    event,
    opts: { domain: string; version: string; quant: string; sha256Expected: string; sizeBytes: number },
  ) => {
    try {
      const deviceJwt = await getStoredDeviceJwtAsync();
      if (!deviceJwt) {
        return { success: false, error: "Device not registered" };
      }
      const apiBase = electronApiBase();
      const result = await downloadAndInstall({
        ...opts,
        deviceJwt,
        apiBase,
        onProgress: (p) => event.sender.send("model:installProgress", p),
      });
      return { success: true, modelName: result.modelName };
    } catch (err) {
      log(`[model] downloadAndInstall error: ${formatUnknownError(err)}`);
      return { success: false, error: String(err) };
    }
  },
);

