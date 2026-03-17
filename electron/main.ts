// Electron main process entrypoint.
// Creates the BrowserWindow and wires IPC handlers that call into
// the local Ollama backend helpers.
import "dotenv/config";

import { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } from "electron";
import path from "path";
import {
  runOllamaCheckStatus,
  runListModels,
  runPullModel,
  runGenerate,
  runDeleteModel,
} from "./ollama-backend";

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;

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
});

process.on("unhandledRejection", (reason) => {
  console.error("[main] Unhandled rejection:", reason);
});

function createTray() {
  if (tray) return;

  // Reuse the existing Fideon logo from the Next.js app for the tray icon.
  // In dev, this resolves to: ../frontend/src/assets/fideon-logo.png
  const iconPath = path.join(
    __dirname,
    "..",
    "..",
    "frontend",
    "src",
    "assets",
    "fideon-logo.png",
  );
  let icon = nativeImage.createFromPath(iconPath);
  if (icon.isEmpty()) {
    icon = nativeImage.createEmpty();
  }

  tray = new Tray(icon);
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
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  // In dev, point to Next.js dev server; in prod, load the built app.
  const startUrl =
    process.env.ELECTRON_START_URL ?? "http://localhost:3000/electron-playground";

  await mainWindow.loadURL(startUrl);
  createTray();
}

app.whenReady().then(createWindow);

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

