import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";

// ── Types ──────────────────────────────────────────────────────────────────────

export type PdfUploadStatus = "uploading" | "uploaded" | "processing" | "done" | "error";

export type PdfUploadRecord = {
  upload_id: string;
  filename: string;
  form_type: string;
  content_type?: string;
  size_bytes: number;
  path?: string;
  status: PdfUploadStatus;
  uploaded_at?: string;
  note?: string;
  error?: string;
};

export type SuryaLine = {
  text: string;
  confidence: number;
  bbox: [number, number, number, number];
};

export type SuryaPage = {
  page: number;
  line_count: number;
  lines: SuryaLine[];
};

export type SuryaField = {
  key: string;
  value: string;
};

export type SuryaOcrResult = {
  total_pages: number;
  pages: SuryaPage[];
  fields: SuryaField[];
  full_text: string;
};

export type SuryaJobStatus =
  | "queued"
  | "loading_model"
  | "processing"
  | "completed"
  | "failed";

export type SuryaJob = {
  job_id: string;
  upload_id: string;
  filename?: string;
  form_type?: string;
  status: SuryaJobStatus;
  queued_at?: string;
  loading_model_at?: string;
  processing_at?: string;
  completed_at?: string;
  error?: string;
  result?: SuryaOcrResult;
};

// ── Auth helper ────────────────────────────────────────────────────────────────

async function authHeader(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not authenticated — please sign in first");
  return { Authorization: `Bearer ${session.access_token}` };
}

// ── Upload ─────────────────────────────────────────────────────────────────────

// ── Smart extraction (detect type → always upload to RunPod) ─────────────────

export type SmartExtractResult = {
  pdf_type: "digital" | "scanned";
  upload_id: string;
  filename: string;
  size_bytes: number;
  status: string;
  form_type: string;
};

/**
 * Unified PDF entry point.
 * - Backend detects digital/scanned for metadata.
 * - Backend uploads to RunPod for both types.
 * - Returns {pdf_type, upload_id, ...}; caller then calls triggerFullExtraction(upload_id).
 */
export async function smartExtractPdf(
  file: File,
  formType: string = "25"
): Promise<SmartExtractResult> {
  const headers = await authHeader();
  const body = new FormData();
  body.append("file", file);

  const resp = await fetch(
    apiUrl(`/api/v1/pdf/smart-extract?form_type=${encodeURIComponent(formType)}`),
    { method: "POST", headers, body }
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Smart extract failed: ${resp.status}`);
  }
  return resp.json();
}

/**
 * Upload a PDF to RunPod via the Fideon backend proxy.
 * Returns the upload record (includes upload_id for OCR triggering).
 */
export async function uploadPdfToRunPod(
  file: File,
  formType: string = "25"
): Promise<PdfUploadRecord> {
  const headers = await authHeader();
  const body = new FormData();
  body.append("file", file);

  const resp = await fetch(
    apiUrl(`/api/v1/pdf/upload?form_type=${encodeURIComponent(formType)}`),
    { method: "POST", headers, body }
  );

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error || `Upload failed: ${resp.status}`);
  }
  return resp.json();
}

/**
 * Poll RunPod for the status of a previously uploaded PDF.
 */
export async function getPdfUploadStatus(uploadId: string): Promise<PdfUploadRecord> {
  const headers = await authHeader();
  const resp = await fetch(
    apiUrl(`/api/v1/pdf/upload/${encodeURIComponent(uploadId)}/status`),
    { headers }
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error || `Status check failed: ${resp.status}`);
  }
  return resp.json();
}

// ── Surya OCR ──────────────────────────────────────────────────────────────────

/**
 * Trigger Surya OCR on an already-uploaded PDF.
 * Returns immediately with {job_id, status: "queued"}.
 * Poll getSuryaJobStatus(job_id) for progress and results.
 */
export async function triggerSuryaOcr(uploadId: string): Promise<SuryaJob> {
  const headers = await authHeader();
  const resp = await fetch(
    apiUrl(`/api/v1/pdf/process/${encodeURIComponent(uploadId)}`),
    { method: "POST", headers }
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error || `Failed to trigger OCR: ${resp.status}`);
  }
  return resp.json();
}

/**
 * Poll Surya OCR job status.
 * status: queued → loading_model → processing → completed | failed
 * When completed, result.fields and result.full_text are populated.
 */
export async function getSuryaJobStatus(jobId: string): Promise<SuryaJob> {
  const headers = await authHeader();
  const resp = await fetch(
    apiUrl(`/api/v1/pdf/process/${encodeURIComponent(jobId)}/status`),
    { headers }
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error || `Job status check failed: ${resp.status}`);
  }
  return resp.json();
}

// ── Full ACORD Extraction ──────────────────────────────────────────────────────

export type AcordFieldValue = {
  value?: string | number | boolean | null;
  confidence?: number;
  source?: string;
} | string | number | boolean | null;

export type AcordExtractionResult = {
  run_id?: string;
  form_type_detected?: string;
  pdf_type?: "digital" | "scanned" | string;
  extracted_json?: Record<string, AcordFieldValue>;
  extracted_fields?: Record<string, AcordFieldValue>;
  fields?: Record<string, AcordFieldValue>;
  warnings?: string[];
  raw_text?: string;
  full_text?: string;
  meta?: Record<string, any>;
  /** Natural language narrative generated by the SLM when ACORD_NL_SUMMARY_ENABLED=true on the backend. */
  natural_language_summary?: string;
  [key: string]: any;
};

/**
 * Run the full ACORD extraction pipeline on an already-uploaded PDF.
 * Runs server-side: Surya OCR → Docling layout → Qwen VL field extraction.
 * This is a long-running call (30s–3min). No polling needed — awaits the result directly.
 */
export async function triggerFullExtraction(
  uploadId: string,
  formTypeHint?: string
): Promise<AcordExtractionResult> {
  const headers = await authHeader();
  const params = formTypeHint ? `?form_type_hint=${encodeURIComponent(formTypeHint)}` : "";
  const resp = await fetch(
    apiUrl(`/api/v1/pdf/extract/${encodeURIComponent(uploadId)}${params}`),
    { method: "POST", headers }
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Extraction failed: ${resp.status}`);
  }
  return resp.json();
}

/**
 * Submit a corrected ACORD extraction as a RunPod fine-tuning sample.
 * Stores: original_fields (what Qwen extracted) + corrected_fields (what user edited)
 * + the PDF already on RunPod (via upload_id). Used later for LoRA fine-tuning.
 */
export async function submitRunpodForTraining(
  uploadId: string,
  originalFields: Record<string, any>,
  correctedFields: Record<string, any>,
  rawText: string,
  formType: string,
): Promise<{ status: string; sample_id?: string; total_samples?: number }> {
  const headers = await authHeader();
  const resp = await fetch(
    apiUrl(`/api/v1/pdf/extract/${encodeURIComponent(uploadId)}/submit-training`),
    {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        original_fields: originalFields,
        corrected_fields: correctedFields,
        raw_text: rawText,
        form_type: formType,
      }),
    }
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Submit failed: ${resp.status}`);
  }
  return resp.json();
}

/** Get count and list of all stored RunPod fine-tuning samples. */
export async function getTrainingSamples(): Promise<{
  total_samples: number;
  pending: number;
  samples: Array<{ sample_id: string; upload_id: string; form_type: string; created_at: string; status: string }>;
}> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl("/api/v1/pdf/training-samples"), { headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Failed: ${resp.status}`);
  }
  return resp.json();
}

/**
 * Sync locally-saved ACORD feedbacks to the RunPod pod as training samples.
 * Called just before fine-tuning starts so RunPod has the data it needs.
 */
export async function syncFeedbacksToRunpod(
  feedbacks: Array<{
    prompt: string;
    original_response: string;
    corrected_response?: string;
    form_type?: string;
    run_id?: string;
  }>
): Promise<{ synced: number; failed: number }> {
  if (feedbacks.length === 0) return { synced: 0, failed: 0 };

  const headers = await authHeader();

  const results = await Promise.allSettled(
    feedbacks.map(async (fb) => {
      let originalFields: Record<string, any> = {};
      let correctedFields: Record<string, any> = {};
      try { originalFields = JSON.parse(fb.original_response || "{}"); } catch { /* not JSON */ }
      try { correctedFields = JSON.parse(fb.corrected_response || "{}"); } catch { /* not JSON */ }
      const r = await fetch(apiUrl("/api/v1/pdf/training-samples"), {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          raw_text: fb.prompt,
          original_fields: originalFields,
          corrected_fields: correctedFields,
          form_type: fb.form_type || "25",
          run_id: fb.run_id ?? null,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    })
  );

  let synced = 0;
  let failed = 0;
  for (const r of results) {
    if (r.status === "fulfilled") synced++; else failed++;
  }
  return { synced, failed };
}

/** Poll the status of a RunPod fine-tuning job. Returns real loss/epoch metrics when done. */
export async function getRunpodJobStatus(jobId: string): Promise<{
  status: string;
  phase?: string;
  version?: number;
  gate_passed?: boolean;
  eval_scores?: Record<string, any>;
  error?: string;
  upload_ids?: string[];
  original_fields_map?: Record<string, Record<string, any>>;
}> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/v1/pdf/finetune/jobs/${encodeURIComponent(jobId)}`), { headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Status check failed: ${resp.status}`);
  }
  return resp.json();
}

export async function startFederatedLearning(): Promise<{
  status: string; job_id?: string; message?: string; versions_found?: number;
}> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl("/api/v1/pdf/federated/start"), {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({}),
    signal: AbortSignal.timeout(35_000),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Federated start failed: ${resp.status}`);
  }
  return resp.json();
}

export async function getFederatedJobStatus(jobId: string): Promise<{
  status: string; phase?: string; version?: number; versions_aggregated?: number[]; error?: string; message?: string;
}> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/v1/pdf/federated/jobs/${encodeURIComponent(jobId)}`), {
    headers,
    signal: AbortSignal.timeout(15_000),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Status check failed: ${resp.status}`);
  }
  return resp.json();
}

export async function getRegisteredAdapterVersions(): Promise<{
  versions: Array<{
    adapter_version: string;
    domain: string;
    quant_levels: string[];
    total_size_bytes: number;
    registered_at: string | null;
  }>;
  error?: string;
  message?: string;
}> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl("/api/v1/pdf/federated/registered-versions"), {
    headers,
    signal: AbortSignal.timeout(15_000),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Failed to fetch registered versions: ${resp.status}`);
  }
  return resp.json();
}

export async function getShareGradientsStatus(): Promise<{
  has_pending: boolean; pending_count?: number; pending_versions?: number[];
}> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl("/api/v1/pdf/share-gradients/status"), { headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Status check failed: ${resp.status}`);
  }
  return resp.json();
}

export async function shareGradients(): Promise<{
  status: string; job_id?: string; message?: string;
}> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl("/api/v1/pdf/share-gradients"), {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Share gradients failed: ${resp.status}`);
  }
  return resp.json();
}

export async function getShareGradientsJobStatus(jobId: string): Promise<{
  status: string; phase?: string; version?: number; error?: string;
}> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl(`/api/v1/pdf/share-gradients/jobs/${encodeURIComponent(jobId)}`), { headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Job status check failed: ${resp.status}`);
  }
  return resp.json();
}

/** Trigger fine-tuning on RunPod with all pending training samples. */
export async function startRunpodFinetune(opts: { acord_run_ids?: string[] } = {}): Promise<{ status: string; job_id?: string; message?: string; total_samples?: number }> {
  const headers = await authHeader();
  const resp = await fetch(apiUrl("/api/v1/pdf/finetune/start"), {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ acord_run_ids: opts.acord_run_ids ?? [] }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.error || `Finetune failed: ${resp.status}`);
  }
  return resp.json();
}
