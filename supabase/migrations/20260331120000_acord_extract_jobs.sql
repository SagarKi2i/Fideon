-- Persist async ACORD extract job status across process restarts/instances.

CREATE TABLE IF NOT EXISTS public.acord_extract_jobs (
  job_id UUID PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed')),
  error TEXT,
  result JSONB
);

-- Self-heal environments where this table already exists with partial columns.
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS job_id UUID;
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS created_by UUID;
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS status TEXT;
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS error TEXT;
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS result JSONB;

-- Best-effort hardening for pre-existing tables.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'acord_extract_jobs_pkey'
      AND conrelid = 'public.acord_extract_jobs'::regclass
  ) THEN
    ALTER TABLE public.acord_extract_jobs ADD PRIMARY KEY (job_id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'acord_extract_jobs_created_by_fkey'
      AND conrelid = 'public.acord_extract_jobs'::regclass
  ) THEN
    ALTER TABLE public.acord_extract_jobs
      ADD CONSTRAINT acord_extract_jobs_created_by_fkey
      FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE CASCADE;
  END IF;
END $$;

ALTER TABLE public.acord_extract_jobs
  ALTER COLUMN status SET DEFAULT 'queued';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'acord_extract_jobs_status_check'
      AND conrelid = 'public.acord_extract_jobs'::regclass
  ) THEN
    ALTER TABLE public.acord_extract_jobs
      ADD CONSTRAINT acord_extract_jobs_status_check
      CHECK (status IN ('queued','running','succeeded','failed'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_acord_extract_jobs_created_by ON public.acord_extract_jobs(created_by);
CREATE INDEX IF NOT EXISTS idx_acord_extract_jobs_status ON public.acord_extract_jobs(status);
CREATE INDEX IF NOT EXISTS idx_acord_extract_jobs_created_at ON public.acord_extract_jobs(created_at DESC);

DROP TRIGGER IF EXISTS update_acord_extract_jobs_updated_at ON public.acord_extract_jobs;
CREATE TRIGGER update_acord_extract_jobs_updated_at
  BEFORE UPDATE ON public.acord_extract_jobs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.acord_extract_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own acord extract jobs" ON public.acord_extract_jobs;
CREATE POLICY "Users can view own acord extract jobs"
  ON public.acord_extract_jobs
  FOR SELECT
  USING (auth.uid() = created_by);

DROP POLICY IF EXISTS "Users can insert own acord extract jobs" ON public.acord_extract_jobs;
CREATE POLICY "Users can insert own acord extract jobs"
  ON public.acord_extract_jobs
  FOR INSERT
  WITH CHECK (auth.uid() = created_by);

DROP POLICY IF EXISTS "Users can update own acord extract jobs" ON public.acord_extract_jobs;
CREATE POLICY "Users can update own acord extract jobs"
  ON public.acord_extract_jobs
  FOR UPDATE
  USING (auth.uid() = created_by)
  WITH CHECK (auth.uid() = created_by);

DROP POLICY IF EXISTS "Admins can manage acord extract jobs" ON public.acord_extract_jobs;
CREATE POLICY "Admins can manage acord extract jobs"
  ON public.acord_extract_jobs
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

