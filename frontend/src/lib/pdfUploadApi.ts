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
