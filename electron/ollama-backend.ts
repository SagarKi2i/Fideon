// Node-side helpers for talking to the local Ollama HTTP API.
// This file runs in the Electron main process environment.
//
// NOTE: This does NOT export anything to the browser directly.
// The preload script exposes a safe bridge via window.electron,
// and calls into these helpers through IPC handlers in main.ts.

const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL ?? "http://127.0.0.1:11434";

export interface OllamaModel {
  name: string;
  size: number;
  digest: string;
  modified_at: string;
}

export interface OllamaStatus {
  installed: boolean;
  running: boolean;
}

export interface PullProgress {
  modelName: string;
  status: string;
  completed?: number;
  total?: number;
}

// Check if Ollama is installed and running by hitting /api/tags
export async function runOllamaCheckStatus(): Promise<OllamaStatus> {
  try {
    const res = await fetch(`${OLLAMA_BASE_URL}/api/tags`);
    if (!res.ok) {
      console.error("[ollama] checkStatus failed:", res.status, res.statusText);
      return { installed: true, running: false };
    }
    return { installed: true, running: true };
  } catch (err) {
    console.error("[ollama] checkStatus error:", err);
    // Could not reach Ollama at all
    return { installed: false, running: false };
  }
}

// List installed models
export async function runListModels(): Promise<{ success: boolean; models: OllamaModel[] }> {
  try {
    const res = await fetch(`${OLLAMA_BASE_URL}/api/tags`);
    if (!res.ok) {
      console.error("[ollama] listModels failed:", res.status, res.statusText);
      return { success: false, models: [] };
    }
    const data = (await res.json()) as { models?: OllamaModel[] };
    return { success: true, models: data.models ?? [] };
  } catch (err) {
    console.error("[ollama] listModels error:", err);
    return { success: false, models: [] };
  }
}

// Pull a model; report progress via callback
export async function runPullModel(
  modelName: string,
  onProgress?: (progress: PullProgress) => void,
): Promise<{ success: boolean }> {
  try {
    const res = await fetch(`${OLLAMA_BASE_URL}/api/pull`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: modelName, stream: true }),
    });

    if (!res.body || !res.ok) {
      return { success: false };
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      for (const line of chunk.split("\n")) {
        if (!line.trim()) continue;
        try {
          const json = JSON.parse(line) as {
            status?: string;
            completed?: number;
            total?: number;
          };
          if (onProgress) {
            onProgress({
              modelName,
              status: json.status ?? "",
              completed: json.completed,
              total: json.total,
            });
          }
        } catch {
          // Ignore malformed JSON lines
        }
      }
    }

    return { success: true };
  } catch (err) {
    console.error("[ollama] pullModel error:", err);
    return { success: false };
  }
}

// Generate using a model; stream chunks back via callback
export async function runGenerate(
  params: { model: string; prompt: string; system?: string },
  onChunk?: (data: { chunk: string; done: boolean }) => void,
): Promise<{ success: boolean; response: string }> {
  try {
    const res = await fetch(`${OLLAMA_BASE_URL}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: params.model,
        prompt: params.prompt,
        system: params.system,
        stream: true,
      }),
    });

    if (!res.body || !res.ok) {
      console.error("[ollama] generate failed:", res.status, res.statusText);
      return { success: false, response: "" };
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullResponse = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      for (const line of chunk.split("\n")) {
        if (!line.trim()) continue;
        try {
          const json = JSON.parse(line) as { response?: string; done?: boolean };
          if (json.response) {
            fullResponse += json.response;
            if (onChunk) {
              onChunk({ chunk: json.response, done: !!json.done });
            }
          }
        } catch {
          // Ignore malformed JSON lines
        }
      }
    }

    if (onChunk) {
      onChunk({ chunk: "", done: true });
    }

    return { success: true, response: fullResponse };
  } catch (err) {
    console.error("[ollama] generate error:", err);
    return { success: false, response: "" };
  }
}

// Delete a model
export async function runDeleteModel(
  modelName: string,
): Promise<{ success: boolean }> {
  try {
    const res = await fetch(`${OLLAMA_BASE_URL}/api/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: modelName }),
    });
    return { success: res.ok };
  } catch (err) {
    console.error("[ollama] deleteModel error:", err);
    return { success: false };
  }
}

