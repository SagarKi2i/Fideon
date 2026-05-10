-- Shared POD extraction workflow:
-- - pod_extraction_runs (user creates, contains extracted_json + raw_text)
-- - pod_extraction_feedback (user/admin corrections)
-- - pod_admin_queue (admin review queue per run)
-- - pod_training_jobs (fine-tuning jobs triggered by admin approval)
-- - pod_eval_results (evaluation metrics persisted per training job)
--
-- This migration is modeled after the existing ACORD tables, but generalized with `pod_id`
-- so the same framework can work for any insurance pod/model/agent.

-- 1) Core run record
CREATE TABLE IF NOT EXISTS public.pod_extraction_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  pod_id TEXT NOT NULL,
  source_filename TEXT,
  source_mime TEXT,

  -- Generic fields: pod extractors may populate these differently.
  raw_text TEXT,
  extracted_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  overall_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,

  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','submitted','needs_admin_review','approved','rejected'))
);

CREATE INDEX IF NOT EXISTS idx_pod_runs_created_by ON public.pod_extraction_runs(created_by);
CREATE INDEX IF NOT EXISTS idx_pod_runs_pod_id ON public.pod_extraction_runs(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_runs_status ON public.pod_extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_pod_runs_created_at ON public.pod_extraction_runs(created_at DESC);

DROP TRIGGER IF EXISTS update_pod_extraction_runs_updated_at ON public.pod_extraction_runs;
CREATE TRIGGER update_pod_extraction_runs_updated_at
  BEFORE UPDATE ON public.pod_extraction_runs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- 2) Feedback/corrections (user + admin)
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

-- 3) Admin queue (one row per run)
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

-- 4) Training jobs triggered by admin approval
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

ALTER TABLE public.pod_extraction_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_extraction_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_admin_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_training_jobs ENABLE ROW LEVEL SECURITY;

-- 5) Evaluation results persisted per training job
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

ALTER TABLE public.pod_eval_results ENABLE ROW LEVEL SECURITY;

-- -------------------------
-- RLS policies (mirroring ACORD)
-- -------------------------

-- pod_extraction_runs policies
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

-- pod_extraction_feedback policies
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

-- pod_admin_queue policies
DROP POLICY IF EXISTS "Admins can manage pod admin queue" ON public.pod_admin_queue;
CREATE POLICY "Admins can manage pod admin queue"
  ON public.pod_admin_queue
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- pod_training_jobs policies
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

-- pod_eval_results policies
DROP POLICY IF EXISTS "Admins can manage pod eval results" ON public.pod_eval_results;
CREATE POLICY "Admins can manage pod eval results"
  ON public.pod_eval_results
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- Constraints for idempotent inserts
-- (Keep history immutable: one eval result row per (job_id, eval_set))
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'pod_eval_results_job_evalset_unique'
  ) THEN
    ALTER TABLE public.pod_eval_results
      ADD CONSTRAINT pod_eval_results_job_evalset_unique UNIQUE (job_id, eval_set);
  END IF;
END
$$;

-- Prevent duplicate training jobs for the same run by default.
-- Note: the runner may create a NEW job row for restarts; the simplest safe behavior is
-- to keep UNIQUE(run_id) like ACORD does today.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'pod_training_jobs_run_id_unique'
  ) THEN
    ALTER TABLE public.pod_training_jobs
      ADD CONSTRAINT pod_training_jobs_run_id_unique UNIQUE (run_id);
  END IF;
END
$$;

