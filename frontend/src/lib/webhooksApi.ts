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

async function authHeadersJson(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    throw notAuthenticatedError();
  }
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export async function fetchWebhooks(): Promise<WebhookRow[]> {
  const res = await fetch(apiUrl("/api/v1/webhooks"), {
    headers: await authHeadersJson(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to load webhooks");
  return (payload.webhooks || []) as WebhookRow[];
}

export async function createWebhook(input: {
  url: string;
  description?: string;
  events?: string[];
}): Promise<{ webhook: WebhookRow; secret: string; note: string }> {
  const res = await fetch(apiUrl("/api/v1/webhooks"), {
    method: "POST",
    headers: await authHeadersJson(),
    body: JSON.stringify({
      url: input.url,
      description: input.description || "",
      events: input.events ?? [],
    }),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to create webhook");
  return payload as { webhook: WebhookRow; secret: string; note: string };
}

export async function updateWebhook(
  id: string,
  patch: Partial<{ url: string; description: string; events: string[]; is_active: boolean }>,
): Promise<void> {
  const res = await fetch(apiUrl(`/api/v1/webhooks/${encodeURIComponent(id)}`), {
    method: "PATCH",
    headers: await authHeadersJson(),
    body: JSON.stringify(patch),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to update webhook");
}

export async function deleteWebhook(id: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/v1/webhooks/${encodeURIComponent(id)}`), {
    method: "DELETE",
    headers: await authHeadersJson(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to delete webhook");
}

export async function rotateWebhookSecret(id: string): Promise<{ secret: string; note: string }> {
  const res = await fetch(apiUrl(`/api/v1/webhooks/${encodeURIComponent(id)}/rotate-secret`), {
    method: "POST",
    headers: await authHeadersJson(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to rotate webhook secret");
  return payload as { secret: string; note: string };
}
