# Fideon Electron

Electron shell for the Fideon OS app. Loads the Next.js frontend and exposes a secure IPC bridge for local Ollama (status, list/pull/generate/delete models).

## Prerequisites

- Node.js 18+
- [Ollama](https://ollama.ai) (optional; required for local model features in the playground)

## Build and run

### 1. Build the Electron main process

From the `electron/` folder:

```bash
cd electron
npm install
npm run build
```

This compiles `main.ts`, `preload.ts`, and `ollama-backend.ts` to `dist/` (e.g. `dist/main.js`, `dist/preload.js`).

### 2. Run with the Next.js dev server

**Option A – Single command from frontend (recommended)**

From the project root, start both the Next dev server and Electron:

```bash
cd frontend
npm install
npm run electron:dev
```

This starts Next at `http://localhost:3000`, waits for it to be ready, then launches Electron and opens `/electron-playground`.

**Option B – Two terminals**

1. **Terminal 1** – start Next:
   ```bash
   cd frontend && npm run dev
   ```

2. **Terminal 2** – build and start Electron:
   ```bash
   cd electron && npm run build && npm start
   ```

Electron will load `http://localhost:3000/electron-playground` by default (override with `ELECTRON_START_URL`).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `ELECTRON_START_URL` | `http://localhost:3000/electron-playground` | URL the app window loads (dev or prod). |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API base URL. |

## Security

- `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true` in the BrowserWindow.
- Only the preload script talks to the main process via IPC; the renderer uses `window.electron` (no Node in the page).

## Project layout

- `main.ts` – entrypoint, window creation, IPC handlers for `ollama:*` and `network:checkStatus`.
- `preload.ts` – contextBridge API for the renderer (`ollama`, `network`, `isElectron`).
- `ollama-backend.ts` – Ollama HTTP client (tags, pull, generate, delete); runs in the main process only.
