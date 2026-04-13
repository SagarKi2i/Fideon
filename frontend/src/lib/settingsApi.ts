import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { buildApiRequestError, notAuthenticatedError, readJsonSafe } from "@/lib/httpErrors";

export interface SettingsPreferences {
  email_notifications: boolean;
  product_updates: boolean;
}

export interface SettingsProfile {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  preferences: SettingsPreferences;
  tenant_id?: string | null;
  tenant_name?: string | null;
  tenant_plan?: string | null;
  /** Tenant-selected signup packs; drives marketplace model visibility when non-empty. */
  tenant_agent_packs?: string[];
  /** null/undefined = unlimited active models (Enterprise). */
  tenant_max_active_models?: number | null;
  /** Distinct model ids activated for any user in the tenant (plan limit applies to this count). */
  tenant_distinct_activated_model_ids?: string[];
}

export interface PersonalApiKeyRow {
  id: string;
  name: string;
  key_prefix: string;
  key_prefix_sha256: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

async function authHeaders(): Promise<Record<string, string>> {
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

export async function fetchSettingsProfile(): Promise<SettingsProfile> {
  const res = await fetch(apiUrl("/api/settings/profile"), {
    headers: await authHeaders(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to load profile");
  return payload.profile as SettingsProfile;
}

export async function updateSettingsProfile(fullName: string, preferences: SettingsPreferences): Promise<void> {
  const res = await fetch(apiUrl("/api/settings/profile"), {
    method: "PATCH",
    headers: await authHeaders(),
    body: JSON.stringify({
      full_name: fullName,
      preferences,
    }),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to update profile");
}

export async function fetchPersonalApiKeys(): Promise<PersonalApiKeyRow[]> {
  const res = await fetch(apiUrl("/api/settings/api-keys"), {
    headers: await authHeaders(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to load API keys");
  return (payload.keys || []) as PersonalApiKeyRow[];
}

export async function createPersonalApiKey(name: string): Promise<{ api_key: string; key: PersonalApiKeyRow }> {
  const res = await fetch(apiUrl("/api/settings/api-keys"), {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ name }),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to create API key");
  return payload as { api_key: string; key: PersonalApiKeyRow };
}

export async function revokePersonalApiKey(keyId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/settings/api-keys/${encodeURIComponent(keyId)}`), {
    method: "DELETE",
    headers: await authHeaders(),
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) throw buildApiRequestError(res, payload, "Failed to revoke API key");
}
