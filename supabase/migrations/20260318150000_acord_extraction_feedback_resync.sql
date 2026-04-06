-- Resync ACORD extraction feedback table (idempotent)
-- Fixes cases where Supabase/PostgREST schema cache misses the table.

-- 1) Table
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

-- 2) RLS + policies
ALTER TABLE public.acord_extraction_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can insert feedback for own runs" ON public.acord_extraction_feedback;
CREATE POLICY "Users can insert feedback for own runs"
  ON public.acord_extraction_feedback
  FOR INSERT
  WITH CHECK (
    auth.uid() = created_by
    AND (
      EXISTS (
        SELECT 1 FROM public.acord_extraction_runs r
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
      SELECT 1 FROM public.acord_extraction_runs r
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

