import { supabase } from "@/integrations/supabase/client";
import { buildApiRequestError, notAuthenticatedError, readJsonSafe } from "@/lib/httpErrors";
import { getApiBaseUrl } from "@/lib/apiBaseUrl";

type Message = { role: "user" | "assistant"; content: string };

interface StreamChatParams {
  messages: Message[];
  conversationId?: string;
  modelId?: string;
  onDelta: (deltaText: string) => void;
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

function flushBuffer(buffer: string, onDelta: (deltaText: string) => void): void {
  if (!buffer.trim()) return;
  const lines = buffer.split("\n");
  for (const rawLine of lines) {
    const jsonStr = normalizeSseLine(rawLine);
    if (!jsonStr || jsonStr === "[DONE]") continue;
    const content = parseSseDelta(jsonStr);
    if (content) onDelta(content);
  }
}

function processChunkBuffer(
  textBuffer: string,
  onDelta: (deltaText: string) => void
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

export async function streamChat({
  messages,
  conversationId,
  modelId,
  onDelta,
  onDone,
  onError,
}: StreamChatParams) {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) {
      throw notAuthenticatedError();
    }

    const base = getApiBaseUrl();
    const vmHostApiUrl =
      typeof window !== "undefined"
        ? `${window.location.protocol}//${window.location.hostname}:8080`
        : "";
    const candidateUrls = Array.from(
      new Set(
        [
          `${base}/api/chat`,
          vmHostApiUrl ? `${vmHostApiUrl}/api/chat` : "",
          "/api/chat",
          "http://localhost:8080/api/chat",
          "http://127.0.0.1:8080/api/chat",
          "http://localhost:8001/api/chat",
          "http://127.0.0.1:8001/api/chat",
        ].filter(Boolean)
      )
    );

    let resp: Response | null = null;
    let lastErrorMessage = "Failed to reach chat endpoint";
    for (const url of candidateUrls) {
      try {
        const candidate = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.access_token}`,
          },
          body: JSON.stringify({ messages, conversationId, modelId }),
        });

        if (candidate.ok) {
          resp = candidate;
          break;
        }

        const payload = await readJsonSafe(candidate);
        const error = buildApiRequestError(candidate, payload, `Request failed with status ${candidate.status}`);
        lastErrorMessage = error.message;
      } catch (e) {
        lastErrorMessage = e instanceof Error ? e.message : "Network error";
      }
    }

    if (!resp) {
      throw new Error(lastErrorMessage);
    }

    if (!resp.body) {
      throw new Error("No response body");
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
  } catch (e) {
    console.error("Stream chat error:", e);
    if (onError) {
      onError(e instanceof Error ? e.message : "Unknown error");
    }
    onDone();
  }
}
