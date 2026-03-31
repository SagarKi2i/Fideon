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

  if (configured) return configured;
  return "http://localhost:8001";
}

export function apiUrl(path: string): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${cleanPath}`;
}
