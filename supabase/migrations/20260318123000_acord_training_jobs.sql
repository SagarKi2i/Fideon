-- ACORD fine-tuning jobs triggered by admin approval

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

ALTER TABLE public.acord_training_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own acord training jobs" ON public.acord_training_jobs;
CREATE POLICY "Users can view own acord training jobs"
  ON public.acord_training_jobs
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.acord_extraction_runs r
      WHERE r.id = acord_training_jobs.run_id AND r.created_by = auth.uid()
    )
    OR public.has_role(auth.uid(), 'admin')
  );

DROP POLICY IF EXISTS "Admins can manage acord training jobs" ON public.acord_training_jobs;
CREATE POLICY "Admins can manage acord training jobs"
  ON public.acord_training_jobs
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

