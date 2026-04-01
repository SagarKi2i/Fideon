-- ACORD extraction workflow: runs, feedback, admin queue

-- 1) Core run record
CREATE TABLE IF NOT EXISTS public.acord_extraction_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  source_filename TEXT,
  source_mime TEXT,

  form_type_detected TEXT,
  raw_text TEXT,
  extracted_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  overall_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,

  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','submitted','needs_admin_review','approved','rejected'))
);

CREATE INDEX IF NOT EXISTS idx_acord_runs_created_by ON public.acord_extraction_runs(created_by);
CREATE INDEX IF NOT EXISTS idx_acord_runs_status ON public.acord_extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_acord_runs_created_at ON public.acord_extraction_runs(created_at DESC);

DROP TRIGGER IF EXISTS update_acord_extraction_runs_updated_at ON public.acord_extraction_runs;
CREATE TRIGGER update_acord_extraction_runs_updated_at
  BEFORE UPDATE ON public.acord_extraction_runs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- 2) Feedback/corrections (user + admin)
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

-- 3) Admin queue (one row per run)
CREATE TABLE IF NOT EXISTS public.acord_admin_queue (
  run_id UUID PRIMARY KEY REFERENCES public.acord_extraction_runs(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  priority INTEGER NOT NULL DEFAULT 0,
  reason TEXT,
  assigned_to UUID REFERENCES auth.users(id) ON DELETE SET NULL,

  state TEXT NOT NULL DEFAULT 'open'
    CHECK (state IN ('open','in_progress','approved','rework'))
);

CREATE INDEX IF NOT EXISTS idx_acord_admin_queue_state ON public.acord_admin_queue(state);
CREATE INDEX IF NOT EXISTS idx_acord_admin_queue_priority ON public.acord_admin_queue(priority DESC);

DROP TRIGGER IF EXISTS update_acord_admin_queue_updated_at ON public.acord_admin_queue;
CREATE TRIGGER update_acord_admin_queue_updated_at
  BEFORE UPDATE ON public.acord_admin_queue
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- RLS
ALTER TABLE public.acord_extraction_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.acord_extraction_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.acord_admin_queue ENABLE ROW LEVEL SECURITY;

-- acord_extraction_runs policies
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

-- acord_extraction_feedback policies
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

-- acord_admin_queue policies
DROP POLICY IF EXISTS "Admins can manage acord admin queue" ON public.acord_admin_queue;
CREATE POLICY "Admins can manage acord admin queue"
  ON public.acord_admin_queue
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

