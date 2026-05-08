-- Add phase marker so status polling can show extraction progress details.

ALTER TABLE public.acord_extract_jobs
  ADD COLUMN IF NOT EXISTS phase TEXT;

UPDATE public.acord_extract_jobs
SET phase = COALESCE(
  phase,
  CASE
    WHEN status = 'queued' THEN 'queued'
    WHEN status = 'running' THEN 'generate_extracting'
    WHEN status = 'succeeded' THEN 'completed'
    WHEN status = 'failed' THEN 'failed'
    ELSE NULL
  END
);

