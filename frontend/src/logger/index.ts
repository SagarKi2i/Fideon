import pino from "pino";

type LogLevel = "fatal" | "error" | "warn" | "info" | "debug" | "trace";

// Fields that should never appear in logs in raw form.
const REDACTED_KEYS = new Set([
  "password",
  "passwd",
  "secret",
  "token",
  "api_key",
  "authorization",
  "ssn",
  "social_security",
  "credit_card",
  "card_number",
  "cvv",
  "dob",
  "date_of_birth",
  "birth_date",
  "full_name",
  "first_name",
  "last_name",
  "mobile",
  "phone",
  "phone_number",
  "address",
]);

function scrubValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((v) => scrubValue(v));
  }
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj)) {
      if (REDACTED_KEYS.has(k.toLowerCase())) {
        out[k] = "[REDACTED]";
      } else {
        out[k] = scrubValue(v);
      }
    }
    return out;
  }
  if (typeof value === "string") {
    // Simple masking for emails; extend with more patterns as needed.
    if (value.includes("@")) {
      const [user, domain] = value.split("@");
      if (user && domain) {
        return `${user[0]}***@${domain}`;
      }
    }
  }
  return value;
}

function scrubPayload(payload: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!payload) return {};
  return scrubValue(payload) as Record<string, unknown>;
}

export const logger = pino({
  level: (process.env.NEXT_PUBLIC_LOG_LEVEL || "info") as LogLevel,
  timestamp: pino.stdTimeFunctions.isoTime,
  browser: {
    // In the browser we log to console; in Node it goes to stdout.
    asObject: true,
  },
});

export const safeLog = {
  info: (msg: string, payload?: Record<string, unknown>) =>
    logger.info(scrubPayload(payload), msg),
  warn: (msg: string, payload?: Record<string, unknown>) =>
    logger.warn(scrubPayload(payload), msg),
  error: (msg: string, payload?: Record<string, unknown>) =>
    logger.error(scrubPayload(payload), msg),
  debug: (msg: string, payload?: Record<string, unknown>) =>
    logger.debug(scrubPayload(payload), msg),
};

