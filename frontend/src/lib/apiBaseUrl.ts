export function getApiBaseUrl(): string {
  const configured = (process.env.NEXT_PUBLIC_API_URL || "").trim();
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
