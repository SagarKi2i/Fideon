-- Extraction -> fine-tuning bootstrap (single migration for fresh DB setup)
-- Safe to run multiple times (idempotent).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------------
-- 0) Helper function dependency guard
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'update_updated_at_column'
  ) THEN
    CREATE OR REPLACE FUNCTION public.update_updated_at_column()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $fn$
    BEGIN
      NEW.updated_at = now();
      RETURN NEW;
    END;
    $fn$;
  END IF;
END
$$;

-- -----------------------------------------------------------------------------
-- 1) Domain / Agent catalog (used by extraction services)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.domain_catalog (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  description TEXT,
  rag_collection TEXT,
  default_model_adapter TEXT,
  data_path TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS public.agent_catalog (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  domain_id TEXT NOT NULL REFERENCES public.domain_catalog(id) ON DELETE CASCADE,
  category TEXT,
  description TEXT,
  system_prompt TEXT,
  output_schema JSONB,
  rag_collection_override TEXT,
  model_adapter_override TEXT,
  tools JSONB,
  is_active BOOLEAN NOT NULL DEFAULT true
);

-- Minimal default entries required by ACORD extraction flow.
INSERT INTO public.domain_catalog (
  id, display_name, description, rag_collection, is_active
)
VALUES (
  'insurance',
  'Insurance',
  'Insurance workflows and extraction agents',
  'insurance_index',
  true
)
ON CONFLICT (id) DO UPDATE
SET
  display_name = EXCLUDED.display_name,
  description = EXCLUDED.description,
  rag_collection = COALESCE(public.domain_catalog.rag_collection, EXCLUDED.rag_collection),
  is_active = true;

INSERT INTO public.agent_catalog (
  id, display_name, domain_id, category, description, system_prompt,
  output_schema, rag_collection_override, model_adapter_override, tools, is_active
)
VALUES (
  'acord_form_understanding',
  'ACORD Form Understanding',
  'insurance',
  'extraction',
  'ACORD extraction and review workflow agent',
  'You are a structured extraction engine for ACORD insurance forms.',
  '{}'::jsonb,
  NULL,
  NULL,
  '{"extraction_strategy":"acord_form_understanding"}'::jsonb,
  true
)
ON CONFLICT (id) DO UPDATE
SET
  display_name = EXCLUDED.display_name,
  domain_id = EXCLUDED.domain_id,
  category = EXCLUDED.category,
  description = EXCLUDED.description,
  system_prompt = COALESCE(public.agent_catalog.system_prompt, EXCLUDED.system_prompt),
  output_schema = COALESCE(public.agent_catalog.output_schema, EXCLUDED.output_schema),
  tools = COALESCE(public.agent_catalog.tools, EXCLUDED.tools),
  is_active = true;

-- -----------------------------------------------------------------------------
-- 2) ACORD workflow tables (runs/feedback/queue/jobs/eval)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.acord_extraction_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  source_filename TEXT,
  source_mime TEXT,
  form_type_detected TEXT,
  raw_text TEXT,
  original_extracted_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  extracted_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  overall_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','submitted','needs_admin_review','approved','rejected'))
);

ALTER TABLE public.acord_extraction_runs
  ADD COLUMN IF NOT EXISTS original_extracted_json JSONB;

UPDATE public.acord_extraction_runs
SET original_extracted_json = COALESCE(original_extracted_json, extracted_json, '{}'::jsonb)
WHERE original_extracted_json IS NULL;

ALTER TABLE public.acord_extraction_runs
  ALTER COLUMN original_extracted_json SET DEFAULT '{}'::jsonb;

ALTER TABLE public.acord_extraction_runs
  ALTER COLUMN original_extracted_json SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_acord_runs_created_by ON public.acord_extraction_runs(created_by);
CREATE INDEX IF NOT EXISTS idx_acord_runs_status ON public.acord_extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_acord_runs_created_at ON public.acord_extraction_runs(created_at DESC);

DROP TRIGGER IF EXISTS update_acord_extraction_runs_updated_at ON public.acord_extraction_runs;
CREATE TRIGGER update_acord_extraction_runs_updated_at
  BEFORE UPDATE ON public.acord_extraction_runs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TABLE IF NOT EXISTS public.acord_extraction_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  run_id UUID NOT NULL REFERENCES public.acord_extraction_runs(id) ON DELETE CASCADE,
  actor_role TEXT NOT NULL CHECK (actor_role IN ('user','admin')),
  thumbs_up BOOLEAN,
  notes TEXT,
  corrected_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_acord_feedback_run_id ON public.acord_extraction_feedback(run_id);
CREATE INDEX IF NOT EXISTS idx_acord_feedback_created_at ON public.acord_extraction_feedback(created_at DESC);

CREATE TABLE IF NOT EXISTS public.acord_admin_queue (
  run_id UUID PRIMARY KEY REFERENCES public.acord_extraction_runs(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  priority INTEGER NOT NULL DEFAULT 0,
  reason TEXT,
  assigned_to UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  state TEXT NOT NULL DEFAULT 'open'
    CHECK (state IN ('open','in_progress','approved','rework','rejected'))
);

CREATE INDEX IF NOT EXISTS idx_acord_admin_queue_state ON public.acord_admin_queue(state);
CREATE INDEX IF NOT EXISTS idx_acord_admin_queue_priority ON public.acord_admin_queue(priority DESC);

DROP TRIGGER IF EXISTS update_acord_admin_queue_updated_at ON public.acord_admin_queue;
CREATE TRIGGER update_acord_admin_queue_updated_at
  BEFORE UPDATE ON public.acord_admin_queue
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TABLE IF NOT EXISTS public.acord_training_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  run_id UUID NOT NULL REFERENCES public.acord_extraction_runs(id) ON DELETE CASCADE,
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','running','completed','failed')),
  dataset_path TEXT,
  output_dir TEXT,
  log_path TEXT,
  error TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_acord_training_jobs_run_id ON public.acord_training_jobs(run_id);
CREATE INDEX IF NOT EXISTS idx_acord_training_jobs_status ON public.acord_training_jobs(status);
CREATE INDEX IF NOT EXISTS idx_acord_training_jobs_created_at ON public.acord_training_jobs(created_at DESC);

DROP TRIGGER IF EXISTS update_acord_training_jobs_updated_at ON public.acord_training_jobs;
CREATE TRIGGER update_acord_training_jobs_updated_at
  BEFORE UPDATE ON public.acord_training_jobs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TABLE IF NOT EXISTS public.acord_eval_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  job_id UUID REFERENCES public.acord_training_jobs(id) ON DELETE SET NULL,
  eval_set TEXT NOT NULL CHECK (eval_set IN ('seen','paraphrased','oos','combined')),
  exact_match DOUBLE PRECISION,
  soft_accuracy DOUBLE PRECISION,
  semantic_sim DOUBLE PRECISION,
  hallucination_rate DOUBLE PRECISION,
  refusal_rate DOUBLE PRECISION,
  metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_acord_eval_results_job_id ON public.acord_eval_results(job_id);
CREATE INDEX IF NOT EXISTS idx_acord_eval_results_created_at ON public.acord_eval_results(created_at DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'acord_eval_results_job_evalset_unique'
  ) THEN
    ALTER TABLE public.acord_eval_results
      ADD CONSTRAINT acord_eval_results_job_evalset_unique UNIQUE (job_id, eval_set);
  END IF;
END
$$;

-- -----------------------------------------------------------------------------
-- 3) Generic POD workflow tables (runs/feedback/queue/jobs/eval)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.pod_extraction_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  pod_id TEXT NOT NULL,
  source_filename TEXT,
  source_mime TEXT,
  raw_text TEXT,
  original_extracted_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  extracted_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  overall_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','submitted','needs_admin_review','approved','rejected'))
);

ALTER TABLE public.pod_extraction_runs
  ADD COLUMN IF NOT EXISTS original_extracted_json JSONB;

UPDATE public.pod_extraction_runs
SET original_extracted_json = COALESCE(original_extracted_json, extracted_json, '{}'::jsonb)
WHERE original_extracted_json IS NULL;

ALTER TABLE public.pod_extraction_runs
  ALTER COLUMN original_extracted_json SET DEFAULT '{}'::jsonb;

ALTER TABLE public.pod_extraction_runs
  ALTER COLUMN original_extracted_json SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pod_runs_created_by ON public.pod_extraction_runs(created_by);
CREATE INDEX IF NOT EXISTS idx_pod_runs_pod_id ON public.pod_extraction_runs(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_runs_status ON public.pod_extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_pod_runs_created_at ON public.pod_extraction_runs(created_at DESC);

DROP TRIGGER IF EXISTS update_pod_extraction_runs_updated_at ON public.pod_extraction_runs;
CREATE TRIGGER update_pod_extraction_runs_updated_at
  BEFORE UPDATE ON public.pod_extraction_runs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TABLE IF NOT EXISTS public.pod_extraction_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  pod_id TEXT NOT NULL,
  run_id UUID NOT NULL REFERENCES public.pod_extraction_runs(id) ON DELETE CASCADE,
  actor_role TEXT NOT NULL CHECK (actor_role IN ('user','admin')),
  thumbs_up BOOLEAN,
  notes TEXT,
  corrected_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_pod_feedback_pod_id ON public.pod_extraction_feedback(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_feedback_run_id ON public.pod_extraction_feedback(run_id);
CREATE INDEX IF NOT EXISTS idx_pod_feedback_created_at ON public.pod_extraction_feedback(created_at DESC);

CREATE TABLE IF NOT EXISTS public.pod_admin_queue (
  run_id UUID PRIMARY KEY REFERENCES public.pod_extraction_runs(id) ON DELETE CASCADE,
  pod_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  priority INTEGER NOT NULL DEFAULT 0,
  reason TEXT,
  assigned_to UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  state TEXT NOT NULL DEFAULT 'open'
    CHECK (state IN ('open','in_progress','approved','rework','rejected'))
);

CREATE INDEX IF NOT EXISTS idx_pod_admin_queue_pod_id ON public.pod_admin_queue(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_admin_queue_state ON public.pod_admin_queue(state);
CREATE INDEX IF NOT EXISTS idx_pod_admin_queue_priority ON public.pod_admin_queue(priority DESC);

DROP TRIGGER IF EXISTS update_pod_admin_queue_updated_at ON public.pod_admin_queue;
CREATE TRIGGER update_pod_admin_queue_updated_at
  BEFORE UPDATE ON public.pod_admin_queue
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TABLE IF NOT EXISTS public.pod_training_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  pod_id TEXT NOT NULL,
  run_id UUID NOT NULL REFERENCES public.pod_extraction_runs(id) ON DELETE CASCADE,
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','running','completed','failed')),
  dataset_path TEXT,
  output_dir TEXT,
  log_path TEXT,
  error TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pod_training_jobs_pod_id ON public.pod_training_jobs(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_training_jobs_run_id ON public.pod_training_jobs(run_id);
CREATE INDEX IF NOT EXISTS idx_pod_training_jobs_status ON public.pod_training_jobs(status);
CREATE INDEX IF NOT EXISTS idx_pod_training_jobs_created_at ON public.pod_training_jobs(created_at DESC);

DROP TRIGGER IF EXISTS update_pod_training_jobs_updated_at ON public.pod_training_jobs;
CREATE TRIGGER update_pod_training_jobs_updated_at
  BEFORE UPDATE ON public.pod_training_jobs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- Keep history rows per run for retraining; remove old unique(run_id) if present.
ALTER TABLE public.pod_training_jobs
  DROP CONSTRAINT IF EXISTS pod_training_jobs_run_id_unique;

CREATE TABLE IF NOT EXISTS public.pod_eval_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  pod_id TEXT NOT NULL,
  job_id UUID REFERENCES public.pod_training_jobs(id) ON DELETE SET NULL,
  eval_set TEXT NOT NULL CHECK (eval_set IN ('seen','paraphrased','oos','combined')),
  exact_match DOUBLE PRECISION,
  soft_accuracy DOUBLE PRECISION,
  semantic_sim DOUBLE PRECISION,
  hallucination_rate DOUBLE PRECISION,
  refusal_rate DOUBLE PRECISION,
  metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_pod_eval_results_pod_id ON public.pod_eval_results(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_eval_results_job_id ON public.pod_eval_results(job_id);
CREATE INDEX IF NOT EXISTS idx_pod_eval_results_created_at ON public.pod_eval_results(created_at DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'pod_eval_results_job_evalset_unique'
  ) THEN
    ALTER TABLE public.pod_eval_results
      ADD CONSTRAINT pod_eval_results_job_evalset_unique UNIQUE (job_id, eval_set);
  END IF;
END
$$;

-- -----------------------------------------------------------------------------
-- 4) RLS policies for extraction/training workflow tables
--    (depends on existing public.has_role(...) from core auth migrations)
-- -----------------------------------------------------------------------------
ALTER TABLE public.acord_extraction_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.acord_extraction_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.acord_admin_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.acord_training_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.acord_eval_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_extraction_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_extraction_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_admin_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_training_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_eval_results ENABLE ROW LEVEL SECURITY;

-- ACORD runs
DROP POLICY IF EXISTS "Users can insert own acord runs" ON public.acord_extraction_runs;
CREATE POLICY "Users can insert own acord runs"
  ON public.acord_extraction_runs
  FOR INSERT
  WITH CHECK (auth.uid() = created_by);

DROP POLICY IF EXISTS "Users can view own acord runs" ON public.acord_extraction_runs;
CREATE POLICY "Users can view own acord runs"
  ON public.acord_extraction_runs
  FOR SELECT
  USING (auth.uid() = created_by);

DROP POLICY IF EXISTS "Users can update own draft acord runs" ON public.acord_extraction_runs;
CREATE POLICY "Users can update own draft acord runs"
  ON public.acord_extraction_runs
  FOR UPDATE
  USING (auth.uid() = created_by AND status IN ('draft','submitted'))
  WITH CHECK (auth.uid() = created_by);

DROP POLICY IF EXISTS "Admins can manage all acord runs" ON public.acord_extraction_runs;
CREATE POLICY "Admins can manage all acord runs"
  ON public.acord_extraction_runs
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- ACORD feedback
DROP POLICY IF EXISTS "Users can insert feedback for own runs" ON public.acord_extraction_feedback;
CREATE POLICY "Users can insert feedback for own runs"
  ON public.acord_extraction_feedback
  FOR INSERT
  WITH CHECK (
    auth.uid() = created_by
    AND (
      EXISTS (
        SELECT 1
        FROM public.acord_extraction_runs r
        WHERE r.id = run_id AND r.created_by = auth.uid()
      )
      OR public.has_role(auth.uid(), 'admin')
    )
  );

DROP POLICY IF EXISTS "Users can view feedback for own runs" ON public.acord_extraction_feedback;
CREATE POLICY "Users can view feedback for own runs"
  ON public.acord_extraction_feedback
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1
      FROM public.acord_extraction_runs r
      WHERE r.id = run_id AND r.created_by = auth.uid()
    )
    OR public.has_role(auth.uid(), 'admin')
  );

DROP POLICY IF EXISTS "Admins can manage all acord feedback" ON public.acord_extraction_feedback;
CREATE POLICY "Admins can manage all acord feedback"
  ON public.acord_extraction_feedback
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- ACORD admin queue
DROP POLICY IF EXISTS "Admins can manage acord admin queue" ON public.acord_admin_queue;
CREATE POLICY "Admins can manage acord admin queue"
  ON public.acord_admin_queue
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- ACORD training jobs
DROP POLICY IF EXISTS "Users can view own acord training jobs" ON public.acord_training_jobs;
CREATE POLICY "Users can view own acord training jobs"
  ON public.acord_training_jobs
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1
      FROM public.acord_extraction_runs r
      WHERE r.id = acord_training_jobs.run_id
        AND r.created_by = auth.uid()
    )
    OR public.has_role(auth.uid(), 'admin')
  );

DROP POLICY IF EXISTS "Admins can manage acord training jobs" ON public.acord_training_jobs;
CREATE POLICY "Admins can manage acord training jobs"
  ON public.acord_training_jobs
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- ACORD eval
DROP POLICY IF EXISTS "Admins can manage acord eval results" ON public.acord_eval_results;
CREATE POLICY "Admins can manage acord eval results"
  ON public.acord_eval_results
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- POD runs
DROP POLICY IF EXISTS "Users can insert own pod runs" ON public.pod_extraction_runs;
CREATE POLICY "Users can insert own pod runs"
  ON public.pod_extraction_runs
  FOR INSERT
  WITH CHECK (auth.uid() = created_by);

DROP POLICY IF EXISTS "Users can view own pod runs" ON public.pod_extraction_runs;
CREATE POLICY "Users can view own pod runs"
  ON public.pod_extraction_runs
  FOR SELECT
  USING (auth.uid() = created_by);

DROP POLICY IF EXISTS "Users can update own draft pod runs" ON public.pod_extraction_runs;
CREATE POLICY "Users can update own draft pod runs"
  ON public.pod_extraction_runs
  FOR UPDATE
  USING (auth.uid() = created_by AND status IN ('draft','submitted'))
  WITH CHECK (auth.uid() = created_by);

DROP POLICY IF EXISTS "Admins can manage all pod runs" ON public.pod_extraction_runs;
CREATE POLICY "Admins can manage all pod runs"
  ON public.pod_extraction_runs
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- POD feedback
DROP POLICY IF EXISTS "Users can insert feedback for own pod runs" ON public.pod_extraction_feedback;
CREATE POLICY "Users can insert feedback for own pod runs"
  ON public.pod_extraction_feedback
  FOR INSERT
  WITH CHECK (
    auth.uid() = created_by
    AND (
      EXISTS (
        SELECT 1
        FROM public.pod_extraction_runs r
        WHERE r.id = run_id
          AND r.created_by = auth.uid()
          AND r.pod_id = pod_id
      )
      OR public.has_role(auth.uid(), 'admin')
    )
  );

DROP POLICY IF EXISTS "Users can view feedback for own pod runs" ON public.pod_extraction_feedback;
CREATE POLICY "Users can view feedback for own pod runs"
  ON public.pod_extraction_feedback
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1
      FROM public.pod_extraction_runs r
      WHERE r.id = run_id
        AND r.created_by = auth.uid()
        AND r.pod_id = pod_id
    )
    OR public.has_role(auth.uid(), 'admin')
  );

DROP POLICY IF EXISTS "Admins can manage all pod feedback" ON public.pod_extraction_feedback;
CREATE POLICY "Admins can manage all pod feedback"
  ON public.pod_extraction_feedback
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- POD admin queue
DROP POLICY IF EXISTS "Admins can manage pod admin queue" ON public.pod_admin_queue;
CREATE POLICY "Admins can manage pod admin queue"
  ON public.pod_admin_queue
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- POD training jobs
DROP POLICY IF EXISTS "Users can view own pod training jobs" ON public.pod_training_jobs;
CREATE POLICY "Users can view own pod training jobs"
  ON public.pod_training_jobs
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1
      FROM public.pod_extraction_runs r
      WHERE r.id = pod_training_jobs.run_id
        AND r.created_by = auth.uid()
        AND r.pod_id = pod_training_jobs.pod_id
    )
    OR public.has_role(auth.uid(), 'admin')
  );

DROP POLICY IF EXISTS "Admins can manage pod training jobs" ON public.pod_training_jobs;
CREATE POLICY "Admins can manage pod training jobs"
  ON public.pod_training_jobs
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- POD eval
DROP POLICY IF EXISTS "Admins can manage pod eval results" ON public.pod_eval_results;
CREATE POLICY "Admins can manage pod eval results"
  ON public.pod_eval_results
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
