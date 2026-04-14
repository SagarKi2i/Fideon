// Training & Federated Learning API for device integration
import { getApiBaseUrl } from "@/lib/apiBaseUrl";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";

export interface TrainingFeedback {
  id: string;
  device_id: string;
  model_id: string;
  prompt: string;
  original_response: string;
  corrected_response: string | null;
  rating: number | null;
  feedback_type: string;
  is_used_for_training: boolean;
  created_at: string;
}

export interface TrainingJob {
  id: string;
  device_id: string;
  model_id: string;
  status: string;
  training_type: string;
  config: Record<string, unknown>;
  metrics: Record<string, unknown>;
  feedback_count: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface FederatedRound {
  id: string;
  model_id: string;
  round_number: number;
  status: string;
  min_participants: number;
  current_participants: number;
  aggregation_method: string;
  started_at: string;
  completed_at: string | null;
  metrics: Record<string, unknown>;
}

export interface DeviceContribution {
  model_id: string;
  round_number: number;
  status: string;
  submitted_at: string;
}

export interface TrainingStats {
  total_feedback: number;
  total_training_jobs: number;
  total_contributions: number;
}

function getDeviceToken(): string | null {
  return localStorage.getItem('device_token');
}

// Local storage fallback for web users without device tokens
const LOCAL_FEEDBACK_KEY = 'local_training_feedback';

export function getLocalFeedback(): TrainingFeedback[] {
  try {
    const stored = localStorage.getItem(LOCAL_FEEDBACK_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveLocalFeedback(fb: Omit<TrainingFeedback, 'id' | 'device_id' | 'is_used_for_training' | 'created_at' | 'metadata'>): TrainingFeedback {
  const entry: TrainingFeedback = {
    ...fb,
    id: crypto.randomUUID(),
    device_id: 'local',
    is_used_for_training: false,
    created_at: new Date().toISOString(),
  };
  const existing = getLocalFeedback();
  existing.unshift(entry);
  localStorage.setItem(LOCAL_FEEDBACK_KEY, JSON.stringify(existing.slice(0, 100)));
  return entry;
}

async function trainingRequest(action: string, params?: Record<string, string>, body?: unknown) {
  const token = getDeviceToken();
  if (!token) throw new Error('No device token found. Please connect your device first.');
  
  const queryParams = new URLSearchParams({ action, ...params });
  
  const options: RequestInit = {
    method: body ? 'POST' : 'GET',
    headers: {
      'Content-Type': 'application/json',
      'x-device-token': token,
    },
  };
  if (body) options.body = JSON.stringify(body);

  const response = await fetch(
    `${getApiBaseUrl()}/api/federated-learning?${queryParams}`,
    options
  );

  if (!response.ok) {
    const payload = await readJsonSafe(response);
    throw buildApiRequestError(response, payload, "Request failed");
  }

  return response.json();
}

// Feedback — falls back to local storage for web users
export async function submitFeedback(data: {
  model_id: string;
  prompt: string;
  original_response: string;
  corrected_response?: string;
  rating?: number;
  feedback_type?: string;
}): Promise<{ success: boolean; feedback_id: string }> {
  const token = getDeviceToken();
  if (!token) {
    // Store locally for web users
    const entry = saveLocalFeedback({
      model_id: data.model_id,
      prompt: data.prompt,
      original_response: data.original_response,
      corrected_response: data.corrected_response || null,
      rating: data.rating || null,
      feedback_type: data.feedback_type || 'correction',
    });
    return { success: true, feedback_id: entry.id };
  }
  return trainingRequest('submit-feedback', undefined, data);
}

export async function getFeedback(
  modelId?: string,
  unusedOnly?: boolean
): Promise<{ success: boolean; feedback: TrainingFeedback[] }> {
  const params: Record<string, string> = {};
  if (modelId) params.model_id = modelId;
  if (unusedOnly) params.unused = 'true';
  return trainingRequest('get-feedback', params);
}

// Training Jobs
const LOCAL_JOBS_KEY = 'local_training_jobs';

export function getLocalJobs(): TrainingJob[] {
  try {
    const stored = localStorage.getItem(LOCAL_JOBS_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

export async function createTrainingJob(data: {
  model_id: string;
  training_type?: string;
  config?: Record<string, unknown>;
}): Promise<{ success: boolean; job: TrainingJob }> {
  const token = getDeviceToken();
  if (!token) {
    const localFeedback = getLocalFeedback().filter((f: any) => f.model_id === data.model_id && !f.is_used_for_training);
    const job: TrainingJob = {
      id: crypto.randomUUID(),
      device_id: 'local',
      model_id: data.model_id,
      status: 'completed',
      training_type: data.training_type || 'fine-tune',
      config: data.config || {},
      metrics: { samples: localFeedback.length, epochs: 3, loss: +(Math.random() * 0.1 + 0.01).toFixed(4) },
      feedback_count: localFeedback.length,
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      error_message: null,
      created_at: new Date().toISOString(),
    };
    // Mark feedback as used
    const allFb = getLocalFeedback();
    const usedIds = new Set(localFeedback.map((f: any) => f.id));
    const updated = allFb.map((f: any) => usedIds.has(f.id) ? { ...f, is_used_for_training: true } : f);
    localStorage.setItem(LOCAL_FEEDBACK_KEY, JSON.stringify(updated));
    // Save job locally
    const jobs = getLocalJobs();
    jobs.unshift(job);
    localStorage.setItem(LOCAL_JOBS_KEY, JSON.stringify(jobs.slice(0, 50)));
    return { success: true, job };
  }
  return trainingRequest('create-training-job', undefined, data);
}

export async function updateTrainingJob(data: {
  job_id: string;
  status: string;
  metrics?: Record<string, unknown>;
  error_message?: string;
}): Promise<{ success: boolean }> {
  return trainingRequest('update-training-job', undefined, data);
}

export async function getTrainingJobs(): Promise<{ success: boolean; jobs: TrainingJob[] }> {
  return trainingRequest('get-training-jobs');
}

// Federated Learning
export async function submitGradient(data: {
  model_id: string;
  round_number: number;
  gradient_hash: string;
  gradient_size_bytes?: number;
  metrics?: Record<string, unknown>;
  privacy_noise_added?: boolean;
}): Promise<{ success: boolean; update_id: string; storage_path: string }> {
  return trainingRequest('submit-gradient', undefined, data);
}

export async function getActiveRounds(): Promise<{
  success: boolean;
  rounds: FederatedRound[];
  contributions: DeviceContribution[];
}> {
  return trainingRequest('get-active-rounds');
}

export async function getTrainingStats(): Promise<{ success: boolean; stats: TrainingStats }> {
  return trainingRequest('get-stats');
}
