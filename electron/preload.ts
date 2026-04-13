// Electron preload script.
// Runs in an isolated context and exposes a safe API on window.electron
// that matches the types used in frontend/src/lib/ollama.ts.

import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electron", {
  isElectron: async () => true,

  ollama: {
    checkStatus: () => ipcRenderer.invoke("ollama:checkStatus"),
    listModels: () => ipcRenderer.invoke("ollama:listModels"),
    pullModel: (modelName: string) =>
      ipcRenderer.invoke("ollama:pullModel", modelName),
    generate: (params: { model: string; prompt: string; system?: string }) =>
      ipcRenderer.invoke("ollama:generate", params),
    deleteModel: (modelName: string) =>
      ipcRenderer.invoke("ollama:deleteModel", modelName),

    onPullProgress: (callback: (data: { modelName: string; status: string; completed?: number; total?: number }) => void) => {
      ipcRenderer.on("ollama:pullProgress", (_event, data) => callback(data));
    },
    removePullProgressListener: () => {
      ipcRenderer.removeAllListeners("ollama:pullProgress");
    },

    onGenerateChunk: (
      callback: (data: { chunk: string; done: boolean }) => void,
    ) => {
      ipcRenderer.on("ollama:generateChunk", (_event, data) => callback(data));
    },
    removeGenerateChunkListener: () => {
      ipcRenderer.removeAllListeners("ollama:generateChunk");
    },
  },

  network: {
    checkStatus: () => ipcRenderer.invoke("network:checkStatus"),
  },

  device: {
    getDeviceId: () => ipcRenderer.invoke("device:getDeviceId"),
    getAuth: () => ipcRenderer.invoke("device:getAuth"),
    clearAuth: () => ipcRenderer.invoke("device:clearAuth"),
    ensureAuth: () => ipcRenderer.invoke("device:ensureAuth"),
  },

  model: {
    checkUpdate: (domain: string) =>
      ipcRenderer.invoke("model:checkUpdate", domain),

    downloadAndInstall: (opts: {
      domain: string;
      version: string;
      quant: string;
      sha256Expected: string;
      sizeBytes: number;
    }) => ipcRenderer.invoke("model:downloadAndInstall", opts),

    onInstallProgress: (callback: (data: {
      phase: "downloading" | "verifying" | "installing";
      bytesReceived?: number;
      totalBytes?: number;
      percent?: number;
      detail?: string;
    }) => void) => {
      ipcRenderer.on("model:installProgress", (_event, data) => callback(data));
    },

    removeInstallProgressListener: () => {
      ipcRenderer.removeAllListeners("model:installProgress");
    },
  },
});

