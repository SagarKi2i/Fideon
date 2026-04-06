-- Pod workflow hardening:
-- 1) Keep immutable original extraction JSON for each run.
-- 2) Allow multiple training jobs per run so retry/retrain history is preserved.

ALTER TABLE public.pod_extraction_runs
  ADD COLUMN IF NOT EXISTS original_extracted_json JSONB;

-- Backfill for existing rows.
UPDATE public.pod_extraction_runs
SET original_extracted_json = COALESCE(original_extracted_json, extracted_json, '{}'::jsonb)
WHERE original_extracted_json IS NULL;

ALTER TABLE public.pod_extraction_runs
  ALTER COLUMN original_extracted_json SET DEFAULT '{}'::jsonb;

-- Remove UNIQUE(run_id) so each rerun can create a new history row.
ALTER TABLE public.pod_training_jobs
  DROP CONSTRAINT IF EXISTS pod_training_jobs_run_id_unique;

