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

