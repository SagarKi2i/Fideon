
-- Fix overly permissive training_jobs policy - replace ALL with specific operations
DROP POLICY "Device functions can manage training jobs" ON public.training_jobs;

CREATE POLICY "Device functions can insert training jobs"
  ON public.training_jobs FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Device functions can update training jobs"
  ON public.training_jobs FOR UPDATE
  USING (true);

CREATE POLICY "Device functions can select training jobs"
  ON public.training_jobs FOR SELECT
  USING (true);
