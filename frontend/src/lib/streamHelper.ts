import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { buildApiRequestError, notAuthenticatedError, readJsonSafe } from "@/lib/httpErrors";

interface StreamOptions {
  onDelta: (delta: string) => void;
  onDone: () => void;
  onError?: (error: string) => void;
}

function parseSseDelta(jsonStr: string): string | null {
  try {
    const parsed = JSON.parse(jsonStr);
    return (parsed.choices?.[0]?.delta?.content as string | undefined) ?? null;
  } catch {
    return null;
  }
}

function normalizeSseLine(line: string): string | null {
  const normalizedLine = line.endsWith("\r") ? line.slice(0, -1) : line;
  if (normalizedLine.startsWith(":") || normalizedLine.trim() === "") return null;
  if (!normalizedLine.startsWith("data: ")) return null;
  return normalizedLine.slice(6).trim();
}

function processChunkBuffer(
  textBuffer: string,
  onDelta: (delta: string) => void
): { textBuffer: string; streamDone: boolean } {
  let buffer = textBuffer;
  let streamDone = false;

  let newlineIndex: number;
  while ((newlineIndex = buffer.indexOf("\n")) !== -1) {
    const rawLine = buffer.slice(0, newlineIndex);
    buffer = buffer.slice(newlineIndex + 1);
    const jsonStr = normalizeSseLine(rawLine);
    if (!jsonStr) continue;
    if (jsonStr === "[DONE]") {
      streamDone = true;
      break;
    }
    const content = parseSseDelta(jsonStr);
    if (content === null) {
      buffer = `${rawLine}\n${buffer}`;
      break;
    }
    onDelta(content);
  }

  return { textBuffer: buffer, streamDone };
}

function flushBuffer(textBuffer: string, onDelta: (delta: string) => void): void {
  if (!textBuffer.trim()) return;
  const lines = textBuffer.split("\n");
  for (const rawLine of lines) {
    const jsonStr = normalizeSseLine(rawLine);
    if (!jsonStr || jsonStr === "[DONE]") continue;
    const content = parseSseDelta(jsonStr);
    if (content) onDelta(content);
  }
}

export async function streamFromEdgeFunction(
  functionName: string,
  body: Record<string, unknown>,
  { onDelta, onDone, onError }: StreamOptions
) {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw notAuthenticatedError();

  const url = apiUrl(`/api/${functionName}`);

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const payload = await readJsonSafe(resp);
    const error = buildApiRequestError(resp, payload, `Request failed: ${resp.status}`);
    if (onError) onError(error.message);
    onDone();
    return;
  }

  if (!resp.body) {
    if (onError) onError("No response body");
    onDone();
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let textBuffer = "";
  let streamDone = false;

  while (!streamDone) {
    const { done, value } = await reader.read();
    if (done) break;
    textBuffer += decoder.decode(value, { stream: true });
    const chunkResult = processChunkBuffer(textBuffer, onDelta);
    textBuffer = chunkResult.textBuffer;
    streamDone = chunkResult.streamDone;
  }

  flushBuffer(textBuffer, onDelta);

  onDone();
}
