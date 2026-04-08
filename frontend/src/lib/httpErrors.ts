export class ApiRequestError extends Error {
  readonly status: number;
  readonly payload: unknown;
  readonly isAuthError: boolean;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.payload = payload;
    this.isAuthError = status === 401 || status === 403;
  }
}

export function notAuthenticatedError(): ApiRequestError {
  return new ApiRequestError("Your session has expired. Please sign in again.", 401);
}

export async function readJsonSafe(response: Response): Promise<any> {
  return response.json().catch(() => ({}));
}

export function buildApiRequestError(
  response: Response,
  payload: any,
  fallbackMessage: string
): ApiRequestError {
  if (response.status === 401) {
    // Not all 401s are "user session expired". Some endpoints intentionally return 401
    // for device-token / device-JWT auth failures. Preserve those server messages.
    const detail =
      payload?.detail ||
      payload?.error ||
      payload?.message;
    if (typeof detail === "string" && detail.trim()) {
      if (/(device jwt|required|invalid device token|device token|pairing code)/i.test(detail)) {
        return new ApiRequestError(detail, 401, payload);
      }
    }
    return new ApiRequestError("Your session has expired. Please sign in again.", 401, payload);
  }
  if (response.status === 403) {
    return new ApiRequestError("You do not have permission to perform this action.", 403, payload);
  }

  const message =
    payload?.detail ||
    payload?.error ||
    payload?.message ||
    fallbackMessage;

  return new ApiRequestError(message, response.status, payload);
}

