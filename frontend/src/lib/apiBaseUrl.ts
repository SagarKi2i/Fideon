/**
 * Browser → FastAPI base URL.
 * - Local backend: leave NEXT_PUBLIC_API_URL unset or `http://localhost:8001`
 * - Backend on RunPod: set NEXT_PUBLIC_API_URL to the pod HTTPS proxy root, e.g.
 *   `https://<pod-id>-<port>.proxy.runpod.net` (no trailing slash)
 */
export function getApiBaseUrl(): string {
  const configuredRaw = (process.env.NEXT_PUBLIC_API_URL || "").trim();
  // Normalize configured base URL so "/api/..." joins never produce "//api/...".
  const configured = configuredRaw.replace(/\/+$/, "");
  const hasWindow = typeof window !== "undefined";
  const host = hasWindow ? window.location.hostname : "";
  const protocol = hasWindow ? window.location.protocol : "http:";
  const isBrowserLocalHost = host === "localhost" || host === "127.0.0.1";

  // If frontend runs on VM host and env still points to localhost, prefer VM backend.
  if (hasWindow && !isBrowserLocalHost) {
    if (!configured || configured.includes("localhost") || configured.includes("127.0.0.1")) {
      return `${protocol}//${host}:8080`;
    }
  }

  if (configured) return stripTrailingSlashes(configured);
  return "http://localhost:8001";
}

export function apiUrl(path: string): string {
  const baseUrl = getApiBaseUrl();
  const cleanPath = sanitizePath(path);
  return `${baseUrl}${cleanPath}`;
}

function stripTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, "");
}

function sanitizePath(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  // Collapse accidental duplicate slashes in the path portion only.
  return normalized.replace(/\/{2,}/g, "/");
}
