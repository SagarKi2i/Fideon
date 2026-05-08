-- Normalize legacy acord_extract_jobs schemas to user_id-based ownership.
-- Safe to run multiple times.

ALTER TABLE public.acord_extract_jobs
  ADD COLUMN IF NOT EXISTS user_id UUID;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'acord_extract_jobs'
      AND column_name = 'created_by'
  ) THEN
    EXECUTE '
      UPDATE public.acord_extract_jobs
      SET user_id = created_by
      WHERE user_id IS NULL
    ';
  END IF;
END $$;

-- Remove rows that cannot be attributed to any user; they break ownership policies.
DELETE FROM public.acord_extract_jobs
WHERE user_id IS NULL;

ALTER TABLE public.acord_extract_jobs
  ALTER COLUMN user_id SET NOT NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'acord_extract_jobs_created_by_fkey'
      AND conrelid = 'public.acord_extract_jobs'::regclass
  ) THEN
    ALTER TABLE public.acord_extract_jobs
      DROP CONSTRAINT acord_extract_jobs_created_by_fkey;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'acord_extract_jobs_user_id_fkey'
      AND conrelid = 'public.acord_extract_jobs'::regclass
  ) THEN
    ALTER TABLE public.acord_extract_jobs
      ADD CONSTRAINT acord_extract_jobs_user_id_fkey
      FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_acord_extract_jobs_user_id
  ON public.acord_extract_jobs(user_id);

