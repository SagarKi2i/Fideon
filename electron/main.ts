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

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;

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

  await createWindow();
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

// IPC: update-check placeholder
ipcMain.handle("app:checkForUpdates", async () => {
  // Placeholder: wire electron-updater or custom logic here later.
  return {
    success: true,
    status: "not_implemented",
    message: "Update checks are not configured yet.",
  };
});

