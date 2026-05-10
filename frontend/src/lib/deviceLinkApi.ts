import { getApiBaseUrl } from "@/lib/apiBaseUrl";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";
import { supabase } from "@/integrations/supabase/client";

export async function linkDeviceById(deviceId: string): Promise<{ success: boolean; device_id: string }> {
  const { data } = await supabase.auth.getSession();
  const accessToken = data.session?.access_token;
  if (!accessToken) {
    throw new Error("Not authenticated");
  }

  const response = await fetch(`${getApiBaseUrl()}/api/v1/devices/link`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ device_id: deviceId }),
  });

  if (!response.ok) {
    const payload = await readJsonSafe(response);
    throw buildApiRequestError(response, payload, "Failed to link device");
  }

  return response.json();
}

