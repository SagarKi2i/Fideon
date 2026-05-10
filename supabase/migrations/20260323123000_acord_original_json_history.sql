-- ACORD workflow parity with generic pod workflow:
-- preserve immutable original extraction JSON for side-by-side review.

ALTER TABLE public.acord_extraction_runs
  ADD COLUMN IF NOT EXISTS original_extracted_json JSONB;

UPDATE public.acord_extraction_runs
SET original_extracted_json = COALESCE(original_extracted_json, extracted_json, '{}'::jsonb)
WHERE original_extracted_json IS NULL;

ALTER TABLE public.acord_extraction_runs
  ALTER COLUMN original_extracted_json SET DEFAULT '{}'::jsonb;

