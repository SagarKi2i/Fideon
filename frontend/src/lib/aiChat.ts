import { supabase } from "@/integrations/supabase/client";

type Message = { role: "user" | "assistant"; content: string };

interface StreamChatParams {
  messages: Message[];
  conversationId?: string;
  modelId?: string;
  onDelta: (deltaText: string) => void;
  onDone: () => void;
  onError?: (error: string) => void;
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
      throw new Error("Not authenticated");
    }

    const configuredApiUrl = (process.env.NEXT_PUBLIC_API_URL || "").trim();
    const vmHostApiUrl =
      typeof window !== "undefined"
        ? `${window.location.protocol}//${window.location.hostname}:8080`
        : "";
    const candidateUrls = Array.from(
      new Set(
        [
          configuredApiUrl ? `${configuredApiUrl}/api/chat` : "",
          vmHostApiUrl ? `${vmHostApiUrl}/api/chat` : "",
          "/api/chat",
          "http://localhost:8080/api/chat",
          "http://127.0.0.1:8080/api/chat",
          "http://localhost:8001/api/chat",
          "http://127.0.0.1:8001/api/chat",
          "http://localhost:8000/api/chat",
          "http://127.0.0.1:8000/api/chat",
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

        const errorData = await candidate.json().catch(() => ({ error: "Unknown error" }));
        lastErrorMessage = errorData.error || `Request failed with status ${candidate.status}`;
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

      let newlineIndex: number;
      while ((newlineIndex = textBuffer.indexOf("\n")) !== -1) {
        let line = textBuffer.slice(0, newlineIndex);
        textBuffer = textBuffer.slice(newlineIndex + 1);

        if (line.endsWith("\r")) line = line.slice(0, -1);
        if (line.startsWith(":") || line.trim() === "") continue;
        if (!line.startsWith("data: ")) continue;

        const jsonStr = line.slice(6).trim();
        if (jsonStr === "[DONE]") {
          streamDone = true;
          break;
        }

        try {
          const parsed = JSON.parse(jsonStr);
          const content = parsed.choices?.[0]?.delta?.content as string | undefined;
          if (content) onDelta(content);
        } catch {
          textBuffer = line + "\n" + textBuffer;
          break;
        }
      }
    }

    // Final flush
    if (textBuffer.trim()) {
      for (let raw of textBuffer.split("\n")) {
        if (!raw) continue;
        if (raw.endsWith("\r")) raw = raw.slice(0, -1);
        if (raw.startsWith(":") || raw.trim() === "") continue;
        if (!raw.startsWith("data: ")) continue;
        const jsonStr = raw.slice(6).trim();
        if (jsonStr === "[DONE]") continue;
        try {
          const parsed = JSON.parse(jsonStr);
          const content = parsed.choices?.[0]?.delta?.content as string | undefined;
          if (content) onDelta(content);
        } catch {}
      }
    }

    onDone();
  } catch (e) {
    console.error("Stream chat error:", e);
    if (onError) {
      onError(e instanceof Error ? e.message : "Unknown error");
    }
    onDone();
  }
}
