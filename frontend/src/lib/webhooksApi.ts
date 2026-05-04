import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { buildApiRequestError, notAuthenticatedError, readJsonSafe } from "@/lib/httpErrors";

export interface WebhookRow {
  id: string;
  tenant_id: string;
  url: string;
  description: string | null;
  events: string[] | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

async function getAccessToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    throw notAuthenticatedError();
  }
  return token;
}

async function authHeadersJson(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function fetchWebhooks(): Promise<WebhookRow[]> {
  if (typeof window !== "undefined" && window.electron?.webhooks?.list) {
    const token = await getAccessToken();
    const result = await window.electron.webhooks.list(token);
    if (!result?.success) {
      throw new Error(result?.error || result?.payload?.error || "Failed to load webhooks");
    }
    return (result.webhooks || []) as WebhookRow[];
  }

  const res = await fetch(apiUrl("/api/v1/webhooks"), { headers: await authHeadersJson() });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to load webhooks");
  return (payload.webhooks || []) as WebhookRow[];
}

export async function createWebhook(input: {
  url: string;
  description?: string;
  events?: string[];
}): Promise<{ webhook: WebhookRow; secret: string; note: string }> {
  if (typeof window !== "undefined" && window.electron?.webhooks?.create) {
    const token = await getAccessToken();
    const result = await window.electron.webhooks.create(token, input);
    if (!result?.success) {
      throw new Error(result?.error || result?.payload?.error || "Failed to create webhook");
    }
    return result as { webhook: WebhookRow; secret: string; note: string };
  }

  const res = await fetch(apiUrl("/api/v1/webhooks"), {
    method: "POST",
    headers: await authHeadersJson(),
    body: JSON.stringify({ url: input.url, description: input.description || "", events: input.events ?? [] }),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to create webhook");
  return payload as { webhook: WebhookRow; secret: string; note: string };
}

export async function updateWebhook(
  id: string,
  patch: Partial<{ url: string; description: string; events: string[]; is_active: boolean }>,
): Promise<void> {
  if (typeof window !== "undefined" && window.electron?.webhooks?.update) {
    const token = await getAccessToken();
    const result = await window.electron.webhooks.update(token, id, patch);
    if (!result?.success) {
      throw new Error(result?.error || result?.payload?.error || "Failed to update webhook");
    }
    return;
  }

  const res = await fetch(apiUrl(`/api/v1/webhooks/${encodeURIComponent(id)}`), {
    method: "PATCH",
    headers: await authHeadersJson(),
    body: JSON.stringify(patch),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to update webhook");
}

export async function deleteWebhook(id: string): Promise<void> {
  if (typeof window !== "undefined" && window.electron?.webhooks?.delete) {
    const token = await getAccessToken();
    const result = await window.electron.webhooks.delete(token, id);
    if (!result?.success) {
      throw new Error(result?.error || result?.payload?.error || "Failed to delete webhook");
    }
    return;
  }

  const res = await fetch(apiUrl(`/api/v1/webhooks/${encodeURIComponent(id)}`), {
    method: "DELETE",
    headers: await authHeadersJson(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to delete webhook");
}

export async function sendTestEvent(
  eventType: string,
  payload?: Record<string, unknown>,
): Promise<{ event_id: string }> {
  if (typeof window !== "undefined" && window.electron?.webhooks?.testEvent) {
    const token = await getAccessToken();
    const result = await window.electron.webhooks.testEvent(token, eventType, payload ?? {});
    if (!result?.success) {
      throw new Error(result?.error || result?.payload?.error || "Failed to send test event");
    }
    return { event_id: result.event_id ?? "" };
  }

  const res = await fetch(apiUrl("/api/v1/webhooks/test-event"), {
    method: "POST",
    headers: await authHeadersJson(),
    body: JSON.stringify({ event_type: eventType, payload: payload ?? {} }),
  });
  const data = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, data, "Failed to send test event");
  return data as { event_id: string };
}

export async function rotateWebhookSecret(id: string): Promise<{ secret: string; note: string }> {
  if (typeof window !== "undefined" && window.electron?.webhooks?.rotateSecret) {
    const token = await getAccessToken();
    const result = await window.electron.webhooks.rotateSecret(token, id);
    if (!result?.success) {
      throw new Error(result?.error || result?.payload?.error || "Failed to rotate webhook secret");
    }
    return result as { secret: string; note: string };
  }

  const res = await fetch(apiUrl(`/api/v1/webhooks/${encodeURIComponent(id)}/rotate-secret`), {
    method: "POST",
    headers: await authHeadersJson(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to rotate webhook secret");
  return payload as { secret: string; note: string };
}
