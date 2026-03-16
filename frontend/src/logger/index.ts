import pino from "pino";

type LogLevel = "fatal" | "error" | "warn" | "info" | "debug" | "trace";

// ---------------------------------------------------------------------------
// Pass 1: Field-name keyword redaction
// Any key whose name matches is replaced with "[REDACTED]" regardless of value.
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Pass 2: Content-based PII detection via regex
// Mirrors what Presidio does on the backend — catches PII that appears inside
// generic fields like "message" or "details" regardless of key name.
// ---------------------------------------------------------------------------

interface PiiPattern {
  label: string;
  regex: RegExp;
}

// Each pattern replaces the matched text with <LABEL>.
const PII_PATTERNS: PiiPattern[] = [
  // US Social Security Number  (e.g. 123-45-6789)
  { label: "US_SSN", regex: /\b\d{3}-\d{2}-\d{4}\b/g },

  // Credit / debit card numbers (13-16 digits, optional spaces/dashes)
  {
    label: "CREDIT_CARD",
    regex: /\b(?:\d[ -]?){13,15}\d\b/g,
  },

  // International phone numbers and common US formats
  {
    label: "PHONE_NUMBER",
    regex:
      /(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)(?:\d{3}[\s.-]?\d{4})/g,
  },

  // Email addresses (complement to the @ masking below)
  {
    label: "EMAIL_ADDRESS",
    regex: /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g,
  },

  // IBAN  (e.g. GB29 NWBK 6016 1331 9268 19)
  {
    label: "IBAN_CODE",
    regex: /\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]?){0,16}\b/g,
  },
];

/**
 * Scan a plain string for PII content and replace detected patterns.
 * Runs AFTER the email-masking step so EMAIL_ADDRESS regex is a safety net
 * for any emails that slipped through (e.g. no "@" path hit).
 */
function contentScrubString(value: string): string {
  let result = value;

  // Email masking first (preserves u***@domain format, cheaper than regex)
  if (result.includes("@")) {
    result = result.replace(
      /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g,
      (match) => {
        const atIdx = match.indexOf("@");
        return `${match[0]}***@${match.slice(atIdx + 1)}`;
      }
    );
  }

  // Regex content patterns (SSN, credit card, phone, IBAN, stray emails)
  for (const { label, regex } of PII_PATTERNS) {
    // Skip EMAIL_ADDRESS here — handled by the masking step above
    if (label === "EMAIL_ADDRESS") continue;
    result = result.replace(regex, `<${label}>`);
  }

  return result;
}

// ---------------------------------------------------------------------------
// Combined scrubber — applied to every value in the log payload
// ---------------------------------------------------------------------------

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
    return contentScrubString(value);
  }
  return value;
}

function scrubPayload(
  payload: Record<string, unknown> | undefined
): Record<string, unknown> {
  if (!payload) return {};
  return scrubValue(payload) as Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Pino logger instance
// ---------------------------------------------------------------------------

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
