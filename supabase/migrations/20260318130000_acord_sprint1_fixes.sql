-- Sprint 1 fixes:
--   1. Add 'rejected' state to acord_admin_queue
--   2. Add UNIQUE(run_id) to acord_training_jobs to prevent duplicate jobs
--   3. Add acord_eval_results table for evaluation metric persistence

-- 1. Expand acord_admin_queue.state to include 'rejected'
ALTER TABLE public.acord_admin_queue
  DROP CONSTRAINT IF EXISTS acord_admin_queue_state_check;

ALTER TABLE public.acord_admin_queue
  ADD CONSTRAINT acord_admin_queue_state_check
  CHECK (state IN ('open', 'in_progress', 'approved', 'rework', 'rejected'));

-- 2. Prevent duplicate training jobs per run
ALTER TABLE public.acord_training_jobs
  DROP CONSTRAINT IF EXISTS acord_training_jobs_run_id_unique;

ALTER TABLE public.acord_training_jobs
  ADD CONSTRAINT acord_training_jobs_run_id_unique UNIQUE (run_id);

-- 3. Eval results table (for Sprint 5 baseline — create now so the schema is stable)
CREATE TABLE IF NOT EXISTS public.acord_eval_results (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

  job_id          UUID REFERENCES public.acord_training_jobs(id) ON DELETE SET NULL,
  eval_set        TEXT NOT NULL CHECK (eval_set IN ('seen', 'paraphrased', 'oos', 'combined')),

  exact_match     DOUBLE PRECISION,
  soft_accuracy   DOUBLE PRECISION,
  semantic_sim    DOUBLE PRECISION,
  hallucination_rate DOUBLE PRECISION,
  refusal_rate    DOUBLE PRECISION,

  -- Raw metrics blob for forward-compatibility
  metrics_json    JSONB NOT NULL DEFAULT '{}'::jsonb,

  notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_acord_eval_job_id ON public.acord_eval_results(job_id);
CREATE INDEX IF NOT EXISTS idx_acord_eval_created_at ON public.acord_eval_results(created_at DESC);

ALTER TABLE public.acord_eval_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can manage acord eval results" ON public.acord_eval_results;
CREATE POLICY "Admins can manage acord eval results"
  ON public.acord_eval_results
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
