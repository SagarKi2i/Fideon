// Ollama service for local model execution
// This service communicates with Ollama running on localhost

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

// Check if we're running in Electron
export async function isElectron(): Promise<boolean> {
  if (typeof window !== 'undefined' && window.electron) {
    return await window.electron.isElectron();
  }
  return false;
}

// Check Ollama installation and running status
export async function checkOllamaStatus(): Promise<OllamaStatus> {
  if (typeof window !== 'undefined' && window.electron) {
    return await window.electron.ollama.checkStatus();
  }
  return { installed: false, running: false };
}

// List all installed models
export async function listOllamaModels(): Promise<OllamaModel[]> {
  if (typeof window !== 'undefined' && window.electron) {
    const result = await window.electron.ollama.listModels();
    return result.success ? result.models : [];
  }
  return [];
}

// Pull (download) a model from Ollama library
export async function pullOllamaModel(
  modelName: string,
  onProgress?: (progress: PullProgress) => void
): Promise<boolean> {
  if (typeof window !== 'undefined' && window.electron) {
    if (onProgress) {
      window.electron.ollama.onPullProgress(onProgress);
    }
    
    const result = await window.electron.ollama.pullModel(modelName);
    
    if (onProgress) {
      window.electron.ollama.removePullProgressListener();
    }
    
    return result.success;
  }
  return false;
}

// Generate text using a local model
export async function generateWithOllama(
  model: string,
  prompt: string,
  systemPrompt?: string,
  onChunk?: (chunk: string) => void
): Promise<string> {
  if (typeof window !== 'undefined' && window.electron) {
    if (onChunk) {
      window.electron.ollama.onGenerateChunk((data: { chunk: string; done: boolean }) => {
        onChunk(data.chunk);
      });
    }
    
    const result = await window.electron.ollama.generate({
      model,
      prompt,
      system: systemPrompt,
    });
    
    if (onChunk) {
      window.electron.ollama.removeGenerateChunkListener();
    }
    
    return result.success ? result.response : '';
  }
  return '';
}

// Delete a model
export async function deleteOllamaModel(modelName: string): Promise<boolean> {
  if (typeof window !== 'undefined' && window.electron) {
    const result = await window.electron.ollama.deleteModel(modelName);
    return result.success;
  }
  return false;
}

// Check network status
export async function checkNetworkStatus(): Promise<boolean> {
  if (typeof window !== 'undefined' && window.electron) {
    const result = await window.electron.network.checkStatus();
    return result.online;
  }
  // Fallback for web version
  return navigator.onLine;
}

// Model name mapping from our system to Ollama models
export const MODEL_MAPPINGS: Record<string, string> = {
  'policy-comparison': 'llama3.2:latest',
  'acord-parser': 'llama3.2:latest',
  'claims-fnol': 'llama3.2:latest',
  'renewal-review': 'llama3.2:latest',
  'document-search': 'llama3.2:latest',
};

// Get Ollama model name for our model ID
export function getOllamaModelName(modelId: string): string {
  return MODEL_MAPPINGS[modelId] || 'llama3.2:latest';
}

// Type declarations for window.electron
declare global {
  interface Window {
    electron?: {
      isElectron: () => Promise<boolean>;
      ollama: {
        checkStatus: () => Promise<OllamaStatus>;
        listModels: () => Promise<{ success: boolean; models: OllamaModel[] }>;
        pullModel: (modelName: string) => Promise<{ success: boolean }>;
        generate: (params: { model: string; prompt: string; system?: string }) => Promise<{ success: boolean; response: string }>;
        deleteModel: (modelName: string) => Promise<{ success: boolean }>;
        onPullProgress: (callback: (data: PullProgress) => void) => void;
        onGenerateChunk: (callback: (data: { chunk: string; done: boolean }) => void) => void;
        removePullProgressListener: () => void;
        removeGenerateChunkListener: () => void;
      };
      network: {
        checkStatus: () => Promise<{ online: boolean }>;
      };
      device?: {
        getDeviceId: () => Promise<{ success: boolean; device_id: string | null; error?: string }>;
        getAuth?: () => Promise<{ success: boolean; device_id: string | null; device_jwt: string | null; error?: string }>;
        clearAuth?: () => Promise<{ success: boolean; error?: string }>;
        ensureAuth?: () => Promise<{ success: boolean; device_id?: string | null; device_jwt?: string | null; error?: string }>;
        getDeviceInfo?: () => Promise<
          | { success: true; machineName: string; machineId: string; platform: string }
          | { success: false; error?: string }
        >;
      };
      webhooks?: {
        getReceiver: () => Promise<{ success: boolean; url?: string; error?: string }>;
        setSigningSecret: (secret: string) => Promise<{ success: boolean; error?: string }>;
        onEvent: (callback: (evt: any) => void) => void;
        removeEventListener: () => void;
      };
      model?: {
        checkUpdate: (domain: string) => Promise<{
          success: boolean;
          available: boolean;
          version?: string;
          minElectronVer?: string;
          rollbackSafe?: boolean;
          artifacts?: Array<{ quant_level: string; sha256: string; size_bytes: number }>;
          error?: string;
        }>;
        downloadAndInstall: (opts: {
          domain: string;
          version: string;
          quant: string;
          sha256Expected: string;
          sizeBytes: number;
        }) => Promise<{ success: boolean; modelName?: string; error?: string }>;
        onInstallProgress: (callback: (data: {
          phase: "downloading" | "verifying" | "installing";
          bytesReceived?: number;
          totalBytes?: number;
          percent?: number;
          detail?: string;
        }) => void) => void;
        removeInstallProgressListener: () => void;
      };
    };
  }
}
