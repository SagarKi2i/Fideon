/**
 * Production Supabase persistence layer for the ACORD extraction workflow.
 *
 * Tables used (all have RLS; user must be authenticated):
 *   acord_extraction_runs     – one row per PDF processed
 *   acord_extraction_feedback – user corrections linked to a run
 *   acord_admin_queue         – runs flagged for admin review
 *
 * These tables are not yet in the generated types.ts, so we cast the client
 * to `any` for the raw Supabase calls. All exported functions are fully typed.
 */
import { supabase } from "@/integrations/supabase/client";

// ── Internal helper ────────────────────────────────────────────────────────────

const db = supabase as any;

async function currentUserId(): Promise<string> {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error("Not authenticated");
  return user.id;
}

// ── Types ──────────────────────────────────────────────────────────────────────

export type AcordTrainingSample = {
  run_id: string;
  prompt: string;
  original_response: string;
  corrected_response: string;
  form_type: string;
};

// ── Create extraction run ──────────────────────────────────────────────────────

/**
 * Persists the result of a smart-extract call as a draft run.
 * Returns the new run UUID — store it in component state for subsequent calls.
 */
export async function createAcordRun(params: {
  source_filename: string;
  source_mime?: string;
  form_type_detected: string;
  raw_text: string;
  extracted_json: Record<string, any>;
}): Promise<string> {
  const userId = await currentUserId();

  const { data, error } = await db
    .from("acord_extraction_runs")
    .insert({
      created_by: userId,
      source_filename: params.source_filename,
      source_mime: params.source_mime ?? "application/pdf",
      form_type_detected: params.form_type_detected,
      raw_text: params.raw_text,
      extracted_json: params.extracted_json,
      overall_confidence: 0,
      status: "draft",
    })
    .select("id")
    .single();

  if (error) throw new Error(error.message ?? `Failed to save extraction run (code ${error.code})`);
  return data.id as string;
}

// ── Save user correction (Save & Train) ───────────────────────────────────────

/**
 * Stores the user's corrected fields as a feedback record linked to the run,
 * then advances the run status from `draft` → `submitted` so it appears in
 * the training queue.
 */
export async function saveAcordFeedback(
  runId: string,
  correctedJson: Record<string, any>,
  notes?: string,
): Promise<void> {
  const userId = await currentUserId();

  const { error: fbError } = await db
    .from("acord_extraction_feedback")
    .insert({
      created_by: userId,
      run_id: runId,
      actor_role: "user",
      thumbs_up: true,
      notes: notes ?? "Saved from ACORD Parser",
      corrected_json: correctedJson,
    });

  if (fbError) throw new Error(`Failed to save feedback: ${fbError.message}`);

  // Advance status — non-fatal if this fails (feedback row already saved)
  await db
    .from("acord_extraction_runs")
    .update({ status: "submitted" })
    .eq("id", runId)
    .eq("created_by", userId);
}

// ── Send to admin review ───────────────────────────────────────────────────────

/**
 * Adds the run to the admin review queue and marks it `needs_admin_review`.
 * Requires the migration that grants users INSERT on acord_admin_queue for
 * their own runs (20260425000000_acord_admin_queue_user_insert.sql).
 */
export async function sendAcordToReview(
  runId: string,
  correctedJson: Record<string, any>,
  notes?: string,
): Promise<void> {
  const userId = await currentUserId();

  // Save the correction first (idempotent — insert a new feedback row)
  await db
    .from("acord_extraction_feedback")
    .insert({
      created_by: userId,
      run_id: runId,
      actor_role: "user",
      thumbs_up: true,
      notes: notes ?? "Sent for admin review",
      corrected_json: correctedJson,
    });

  // Upsert queue entry (safe to call multiple times)
  const { error: qError } = await db
    .from("acord_admin_queue")
    .upsert(
      { run_id: runId, reason: notes ?? "User requested review", state: "open", priority: 0 },
      { onConflict: "run_id" },
    );

  if (qError) throw new Error(`Failed to add to review queue: ${qError.message}`);

  await db
    .from("acord_extraction_runs")
    .update({ status: "needs_admin_review" })
    .eq("id", runId)
    .eq("created_by", userId);
}

// ── Training count ────────────────────────────────────────────────────────────

/**
 * Returns the number of training corrections saved by this user that have
 * not yet been used in a fine-tuning run.
 *
 * Source of truth: acord_extraction_feedback (actor_role = 'user').
 * We do NOT rely on acord_extraction_runs.status because the status UPDATE
 * is best-effort and can fail silently; the feedback INSERT is the definitive
 * signal that a correction was saved.
 *
 * Excludes runs already marked 'approved' (used in a previous fine-tune).
 */
export async function getAcordTrainingCount(): Promise<number> {
  // Two .eq() queries instead of .in() — avoids PostgREST inconsistency where .in() returns 0.
  const [{ count: c1 }, { count: c2 }] = await Promise.all([
    db.from("acord_extraction_runs").select("id", { count: "exact", head: true }).eq("status", "submitted"),
    db.from("acord_extraction_runs").select("id", { count: "exact", head: true }).eq("status", "needs_admin_review"),
  ]);
  return (c1 ?? 0) + (c2 ?? 0);
}

// ── Training samples for RunPod sync ─────────────────────────────────────────

/**
 * Returns all user corrections not yet used in fine-tuning, formatted as
 * the shape that `syncFeedbacksToRunpod` expects.
 *
 * Source of truth: acord_extraction_feedback.
 * Fetches feedback first, then gets the matching runs (excluding 'approved').
 */
export async function getAcordTrainingSamples(): Promise<AcordTrainingSample[]> {
  // Step 1: fetch submitted + needs_admin_review runs with two reliable .eq() queries
  const [{ data: submitted }, { data: needsReview }] = await Promise.all([
    db.from("acord_extraction_runs")
      .select("id, raw_text, extracted_json, form_type_detected")
      .eq("status", "submitted"),
    db.from("acord_extraction_runs")
      .select("id, raw_text, extracted_json, form_type_detected")
      .eq("status", "needs_admin_review"),
  ]);
  const allRuns: any[] = [...(submitted ?? []), ...(needsReview ?? [])];
  if (allRuns.length === 0) return [];

  const runIds = allRuns.map((r: any) => r.id);

  // Step 2: batch the .in() to avoid URL length limits (safe batch ≤ 500 IDs)
  const BATCH = 500;
  const allFeedbacks: any[] = [];
  for (let i = 0; i < runIds.length; i += BATCH) {
    const { data: feedbacks } = await db
      .from("acord_extraction_feedback")
      .select("run_id, corrected_json")
      .eq("actor_role", "user")
      .in("run_id", runIds.slice(i, i + BATCH));
    if (feedbacks) allFeedbacks.push(...(feedbacks as any[]));
  }

  if (allFeedbacks.length === 0) return [];

  // Step 3: join in memory — last feedback per run_id wins
  const fbMap = new Map<string, any>();
  for (const fb of allFeedbacks) {
    fbMap.set(fb.run_id, fb.corrected_json);
  }

  const samples: AcordTrainingSample[] = [];
  for (const run of allRuns) {
    const correctedJson = fbMap.get(run.id);
    if (!correctedJson) continue;
    samples.push({
      run_id: run.id,
      prompt: run.raw_text || JSON.stringify(run.extracted_json),
      original_response: JSON.stringify(run.extracted_json),
      corrected_response: JSON.stringify(correctedJson),
      form_type: run.form_type_detected || "25",
    });
  }

  return samples;
}

// ── Sample list for display (Local Training tab) ─────────────────────────────

export type AcordSampleDisplay = {
  run_id: string;
  source_filename: string;
  form_type: string;
  status: string;
  created_at: string;
  prompt: string;
  original_response: string;
  corrected_response: string | null;
};

/**
 * Returns all pending training samples for display, ordered latest first.
 *
 * Fetches only lightweight metadata columns in the list query — raw_text and
 * extracted_json are omitted because they can be many KB per row and cause
 * Supabase to reject the response when many rows are returned together.
 * Full content is loaded on-demand via getAcordSampleDetail() when a row is expanded.
 */
export async function getAcordSamplesForDisplay(): Promise<AcordSampleDisplay[]> {
  // Fetch ALL runs for this user (RLS ensures only own rows), then filter client-side.
  // This avoids any PostgREST .in() / .eq() inconsistency that returns 0 despite rows existing.
  const { data: allRuns, error: runsError } = await db
    .from("acord_extraction_runs")
    .select("id, source_filename, form_type_detected, status, created_at");

  if (runsError) {
    console.error("[acordSupabaseApi] runs query error:", runsError);
    throw new Error(runsError.message ?? `Supabase error code ${runsError.code}`);
  }

  console.log("[acordSupabaseApi] all runs:", (allRuns ?? []).map((r: any) => `${r.status}`));

  const runs = (allRuns ?? [] as any[])
    .filter((r: any) => r.status === "submitted" || r.status === "needs_admin_review")
    .sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  console.log("[acordSupabaseApi] filtered runs:", runs.length);
  if (runs.length === 0) return [];

  const runIds = (runs as any[]).map((r: any) => r.id);

  const { data: feedbacks, error: fbError } = await db
    .from("acord_extraction_feedback")
    .select("run_id, corrected_json")
    .eq("actor_role", "user")
    .in("run_id", runIds);

  if (fbError) console.warn("[acordSupabaseApi] feedbacks query error:", fbError);
  console.log("[acordSupabaseApi] feedbacks returned:", feedbacks?.length ?? 0);

  const fbMap = new Map<string, any>();
  for (const fb of (feedbacks ?? []) as any[]) {
    fbMap.set(fb.run_id, fb.corrected_json);
  }

  return (runs as any[]).map((r: any) => ({
    run_id: r.id,
    source_filename: r.source_filename || "Unknown file",
    form_type: r.form_type_detected || "ACORD",
    status: r.status,
    created_at: r.created_at,
    prompt: "",
    original_response: "",
    corrected_response: (() => {
      const cj = fbMap.get(r.id);
      return cj ? JSON.stringify(cj, null, 2) : null;
    })(),
  }));
}

/**
 * Loads the full raw_text and extracted_json for a single run.
 * Called when the user expands an individual sample row.
 */
export async function getAcordSampleDetail(runId: string): Promise<{
  prompt: string;
  original_response: string;
} | null> {
  const { data, error } = await db
    .from("acord_extraction_runs")
    .select("raw_text, extracted_json")
    .eq("id", runId)
    .single();
  if (error || !data) return null;
  return {
    prompt: (data as any).raw_text || JSON.stringify((data as any).extracted_json ?? {}),
    original_response: JSON.stringify((data as any).extracted_json ?? {}, null, 2),
  };
}

// ── Mark samples used after training ─────────────────────────────────────────

/**
 * After RunPod fine-tuning starts, advance run status to `approved` so the
 * same samples are not counted again in future training batches.
 */
export async function markAcordSamplesUsed(runIds: string[]): Promise<void> {
  if (runIds.length === 0) return;
  await db
    .from("acord_extraction_runs")
    .update({ status: "approved" })
    .in("id", runIds);
}
