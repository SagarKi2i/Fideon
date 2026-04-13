/**
 * Model updater — handles the full GGUF download and install flow.
 *
 * Flow:
 *   1. checkForModelUpdate()  — asks backend if a new version is available (canary-gated)
 *   2. downloadAndInstall()   — downloads GGUF, verifies SHA-256 + GPG sig, runs `ollama create`
 *
 * Called from main.ts via IPC handlers: model:checkUpdate / model:downloadAndInstall
 */

import crypto from "node:crypto";
import { execFile } from "node:child_process";
import fs from "node:fs";
import https from "node:https";
import http from "node:http";
import path from "node:path";
import { promisify } from "node:util";
import { app } from "electron";

const execFileAsync = promisify(execFile);

export interface UpdateCheckResult {
  available: boolean;
  version?: string;
  minElectronVer?: string;
  rollbackSafe?: boolean;
  artifacts?: Array<{
    quant_level: string;
    sha256: string;
    size_bytes: number;
  }>;
}

export interface DownloadProgress {
  phase: "downloading" | "verifying" | "installing";
  bytesReceived?: number;
  totalBytes?: number;
  percent?: number;
  detail?: string;
}

export interface InstallResult {
  modelName: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function modelsDir(): string {
  const dir = path.join(app.getPath("userData"), "fideon-models");
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function authedHeaders(deviceJwt: string): Record<string, string> {
  return { Authorization: `Bearer ${deviceJwt}` };
}

/**
 * Download a URL to a local file, calling onProgress with byte counts.
 * Follows up to 5 redirects. Uses http/https for streaming progress.
 */
async function downloadFile(
  url: string,
  destPath: string,
  totalBytes: number,
  onProgress: (received: number, total: number) => void,
): Promise<void> {
  const MAX_REDIRECTS = 5;

  const doRequest = (currentUrl: string, redirectsLeft: number): Promise<void> =>
    new Promise((resolve, reject) => {
      const proto = currentUrl.startsWith("https://") ? https : http;
      const file = fs.createWriteStream(destPath);
      let received = 0;

      proto
        .get(currentUrl, (res) => {
          // Follow redirects
          if (
            res.statusCode &&
            res.statusCode >= 300 &&
            res.statusCode < 400 &&
            res.headers.location
          ) {
            file.destroy();
            if (redirectsLeft <= 0) {
              reject(new Error(`Too many redirects downloading ${currentUrl}`));
              return;
            }
            const next = res.headers.location.startsWith("http")
              ? res.headers.location
              : new URL(res.headers.location, currentUrl).toString();
            resolve(doRequest(next, redirectsLeft - 1));
            return;
          }

          if (res.statusCode !== 200) {
            file.destroy();
            reject(new Error(`Download failed: HTTP ${String(res.statusCode)} for ${currentUrl}`));
            return;
          }

          res.on("data", (chunk: Buffer) => {
            received += chunk.length;
            onProgress(received, totalBytes);
          });

          res.pipe(file);

          file.on("finish", () => resolve());

          file.on("error", (err) => {
            fs.unlink(destPath, () => {});
            reject(err);
          });

          res.on("error", (err) => {
            file.destroy();
            fs.unlink(destPath, () => {});
            reject(err);
          });
        })
        .on("error", (err) => {
          file.destroy();
          reject(err);
        });
    });

  return doRequest(url, MAX_REDIRECTS);
}

/**
 * Compute SHA-256 of a file and return the hex digest.
 */
async function sha256File(filePath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    const stream = fs.createReadStream(filePath);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("end", () => resolve(hash.digest("hex")));
    stream.on("error", reject);
  });
}

/**
 * Verify GPG detached signature. Requires `gpg` in PATH with the public key imported.
 * Returns true if valid, false if gpg is not available (non-fatal on user machines).
 * Throws if gpg is available but signature is invalid.
 */
async function verifyGpgSig(filePath: string, sigPath: string): Promise<boolean> {
  try {
    await execFileAsync("gpg", ["--verify", sigPath, filePath]);
    return true;
  } catch (err: any) {
    // gpg not found on this machine — skip silently (SHA-256 is the primary check)
    if ((err.code === "ENOENT") || String(err.message).includes("not found")) {
      return false;
    }
    // gpg is present but signature is BAD — this is a real error
    throw new Error(`GPG signature verification failed: ${String(err.stderr || err.message)}`);
  }
}

// ── Public API ───────────────────────────────────────────────────────────────

/**
 * Ask the backend if a new model version is available for this device.
 * The backend applies canary_pct gating — device may get { available: false }.
 */
export async function checkForModelUpdate(opts: {
  domain: string;
  deviceId: string;
  deviceJwt: string;
  apiBase: string;
}): Promise<UpdateCheckResult> {
  const params = new URLSearchParams({ domain: opts.domain, device_id: opts.deviceId });
  const res = await fetch(`${opts.apiBase}/api/v1/adapter/latest?${params.toString()}`, {
    headers: authedHeaders(opts.deviceJwt),
  });

  if (!res.ok) {
    throw new Error(`Update check failed: HTTP ${res.status}`);
  }

  const data = (await res.json()) as any;

  if (!data.available) {
    return { available: false };
  }

  return {
    available: true,
    version: data.adapter_version,
    minElectronVer: data.min_electron_ver,
    rollbackSafe: data.rollback_safe,
    artifacts: data.artifacts,
  };
}

/**
 * Download a GGUF artifact, verify it, and import it into Ollama.
 *
 * Steps:
 *   1. GET /api/v1/adapter/download-url  → fresh presigned URL (1h)
 *   2. Download GGUF to userData/fideon-models/
 *   3. Download .sig file
 *   4. Verify SHA-256 matches manifest
 *   5. Verify GPG signature (if gpg available)
 *   6. ollama create {modelName} -f Modelfile
 *   7. Clean up temp files
 */
export async function downloadAndInstall(opts: {
  domain: string;
  version: string;
  quant: string;
  sha256Expected: string;   // "sha256:<hex>" format from adapter_registry
  sizeBytes: number;
  deviceJwt: string;
  apiBase: string;
  onProgress: (p: DownloadProgress) => void;
}): Promise<InstallResult> {
  const { domain, version, quant, sha256Expected, sizeBytes, deviceJwt, apiBase, onProgress } = opts;

  // Derive a stable Ollama model name: e.g. "broker-1.2.0-q5_k_m"
  const modelName = `${domain}-${version}-${quant}`;
  const dir = path.join(modelsDir(), domain, version);
  fs.mkdirSync(dir, { recursive: true });

  const ggufPath = path.join(dir, `model-${quant}.gguf`);
  const sigPath  = path.join(dir, `model-${quant}.gguf.sig`);
  const modelfilePath = path.join(dir, "Modelfile");

  // ── Step 1: Get fresh presigned URL ──────────────────────────────────────
  const urlParams = new URLSearchParams({ domain, version, quant });
  const urlRes = await fetch(`${apiBase}/api/v1/adapter/download-url?${urlParams.toString()}`, {
    headers: authedHeaders(deviceJwt),
  });
  if (!urlRes.ok) {
    throw new Error(`Failed to get download URL: HTTP ${urlRes.status}`);
  }
  const { url: ggufUrl } = (await urlRes.json()) as { url: string };

  // ── Step 2: Get presigned URL for .sig file ───────────────────────────────
  const sigParams = new URLSearchParams({ domain, version, quant, sig: "true" });
  const sigUrlRes = await fetch(`${apiBase}/api/v1/adapter/download-url?${sigParams.toString()}`, {
    headers: authedHeaders(deviceJwt),
  });
  if (!sigUrlRes.ok) {
    throw new Error(`Failed to get sig download URL: HTTP ${sigUrlRes.status}`);
  }
  const { url: sigUrl } = (await sigUrlRes.json()) as { url: string };

  // ── Step 3: Download GGUF ────────────────────────────────────────────────
  onProgress({ phase: "downloading", bytesReceived: 0, totalBytes: sizeBytes, percent: 0 });

  await downloadFile(ggufUrl, ggufPath, sizeBytes, (received, total) => {
    onProgress({
      phase: "downloading",
      bytesReceived: received,
      totalBytes: total,
      percent: Math.floor((received / total) * 100),
    });
  });

  // ── Step 4: Download .sig file ───────────────────────────────────────────
  onProgress({ phase: "downloading", detail: "Downloading signature file..." });
  await downloadFile(sigUrl, sigPath, 0, () => {});

  // ── Step 5: Verify SHA-256 ───────────────────────────────────────────────
  onProgress({ phase: "verifying", detail: "Verifying SHA-256..." });

  const actualHex = await sha256File(ggufPath);
  const expectedHex = sha256Expected.replace(/^sha256:/, "");
  if (actualHex !== expectedHex) {
    fs.rmSync(dir, { recursive: true, force: true });
    throw new Error(
      `SHA-256 mismatch — file may be corrupted.\nExpected: ${expectedHex}\nGot:      ${actualHex}`,
    );
  }

  // ── Step 6: Verify GPG signature (best-effort) ───────────────────────────
  onProgress({ phase: "verifying", detail: "Verifying GPG signature..." });
  const gpgOk = await verifyGpgSig(ggufPath, sigPath);
  if (!gpgOk) {
    // gpg not installed on this machine — SHA-256 is sufficient for integrity
    onProgress({ phase: "verifying", detail: "GPG not available — skipping signature check" });
  }

  // ── Step 7: Import into Ollama ───────────────────────────────────────────
  onProgress({ phase: "installing", detail: `Running ollama create ${modelName}...` });

  fs.writeFileSync(modelfilePath, `FROM ${ggufPath}\n`, "utf8");

  try {
    await execFileAsync("ollama", ["create", modelName, "-f", modelfilePath]);
  } catch (err: any) {
    throw new Error(`ollama create failed: ${String(err.stderr || err.message)}`);
  }

  // ── Cleanup ──────────────────────────────────────────────────────────────
  // Ollama copies the model into its own store — temp files can be removed
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {
    // non-fatal
  }

  onProgress({ phase: "installing", detail: `Model ${modelName} ready` });
  return { modelName };
}
