// Compute a SHA-256 integrity hash for auth_audit rows.
// IMPORTANT: Do NOT include PII like email in the hash input.

export interface AuditHashInput {
  user_id: string;
  role: string;
  event: string;
  action_code?: string | null;
  outcome_code?: number | null;
  resource_type?: string | null;
  resource_id?: string | null;
  created_at: string;
}

async function sha256Hex(data: string): Promise<string> {
  if (typeof window === "undefined" || !window.crypto?.subtle) {
    // Fallback for environments without Web Crypto; return empty string.
    return "";
  }

  const encoder = new TextEncoder();
  const bytes = encoder.encode(data);
  const digest = await window.crypto.subtle.digest("SHA-256", bytes);
  const hashArray = Array.from(new Uint8Array(digest));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function computeAuditIntegrityHash(input: AuditHashInput): Promise<string> {
  const payload = {
    user_id: input.user_id,
    role: input.role,
    event: input.event,
    action_code: input.action_code || "",
    outcome_code: typeof input.outcome_code === "number" ? input.outcome_code : "",
    resource_type: input.resource_type || "",
    resource_id: input.resource_id || "",
    created_at: input.created_at,
  };

  const serialized = JSON.stringify(payload);
  return sha256Hex(serialized);
}

