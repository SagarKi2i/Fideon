-- =============================================================================
-- Phase 1: Extraction
-- Tracks document extraction jobs that produce raw training samples.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Reuse or create the updated_at trigger function
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- fl_extraction_jobs
-- One row per document submitted for extraction (PDF, image, etc.)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fl_extraction_jobs (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  tenant_id        UUID        REFERENCES auth.users(id) ON DELETE SET NULL,

  source_filename  TEXT        NOT NULL,
  source_mime      TEXT        NOT NULL DEFAULT 'application/pdf',
  form_type        TEXT,                          -- e.g. 'acord_25', 'acord_125'
  storage_key      TEXT,                          -- SeaweedFS object key

  status           TEXT        NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','running','completed','failed')),

  raw_text         TEXT,
  extracted_json   JSONB       NOT NULL DEFAULT '{}'::JSONB,
  confidence       FLOAT8      NOT NULL DEFAULT 0,

  ocr_engine       TEXT        NOT NULL DEFAULT 'surya',
  model_version    TEXT,

  error            TEXT,
  started_at       TIMESTAMPTZ,
  finished_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_fl_extr_jobs_created_by   ON public.fl_extraction_jobs(created_by);
CREATE INDEX IF NOT EXISTS idx_fl_extr_jobs_status       ON public.fl_extraction_jobs(status);
CREATE INDEX IF NOT EXISTS idx_fl_extr_jobs_form_type    ON public.fl_extraction_jobs(form_type);
CREATE INDEX IF NOT EXISTS idx_fl_extr_jobs_created_at   ON public.fl_extraction_jobs(created_at DESC);

DROP TRIGGER IF EXISTS trg_fl_extr_jobs_updated_at ON public.fl_extraction_jobs;
CREATE TRIGGER trg_fl_extr_jobs_updated_at
  BEFORE UPDATE ON public.fl_extraction_jobs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- fl_extraction_samples
-- Individual field-level outputs from an extraction job.
-- These become the raw material for SFT training samples after admin approval.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fl_extraction_samples (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  job_id           UUID        NOT NULL REFERENCES public.fl_extraction_jobs(id) ON DELETE CASCADE,

  field_name       TEXT        NOT NULL,
  predicted_value  TEXT,
  corrected_value  TEXT,                          -- set after human review
  confidence       FLOAT8,
  evidence_text    TEXT,                          -- snippet from raw_text

  is_approved      BOOLEAN     NOT NULL DEFAULT false,
  reviewed_by      UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
  reviewed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_fl_extr_samples_job_id     ON public.fl_extraction_samples(job_id);
CREATE INDEX IF NOT EXISTS idx_fl_extr_samples_approved   ON public.fl_extraction_samples(is_approved);
CREATE INDEX IF NOT EXISTS idx_fl_extr_samples_created_at ON public.fl_extraction_samples(created_at DESC);

-- RLS
ALTER TABLE public.fl_extraction_jobs    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fl_extraction_samples ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own extraction jobs"    ON public.fl_extraction_jobs;
CREATE POLICY "Users see own extraction jobs"
  ON public.fl_extraction_jobs FOR SELECT
  USING (auth.uid() = created_by OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Users insert own extraction jobs" ON public.fl_extraction_jobs;
CREATE POLICY "Users insert own extraction jobs"
  ON public.fl_extraction_jobs FOR INSERT
  WITH CHECK (auth.uid() = created_by);

DROP POLICY IF EXISTS "Admins manage extraction jobs"    ON public.fl_extraction_jobs;
CREATE POLICY "Admins manage extraction jobs"
  ON public.fl_extraction_jobs FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Admins manage extraction samples" ON public.fl_extraction_samples;
CREATE POLICY "Admins manage extraction samples"
  ON public.fl_extraction_samples FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
