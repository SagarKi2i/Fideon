-- FNF-186: Workflow version history (last 10) + restore-to-version

CREATE TABLE IF NOT EXISTS public.workflow_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_id UUID NOT NULL REFERENCES public.workflows(id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  sop_text TEXT NOT NULL,
  category TEXT,
  parsed_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_versions_workflow_id
  ON public.workflow_versions(workflow_id, version_number DESC);

ALTER TABLE public.workflow_versions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own workflow versions"
  ON public.workflow_versions FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.workflows w
      WHERE w.id = workflow_id AND w.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own workflow versions"
  ON public.workflow_versions FOR INSERT
  WITH CHECK (created_by = auth.uid());

-- Trigger: snapshot current workflow state before UPDATE, keep last 10 versions
CREATE OR REPLACE FUNCTION public.snapshot_workflow_version()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  next_version INTEGER;
BEGIN
  SELECT COALESCE(MAX(version_number), 0) + 1
    INTO next_version
    FROM public.workflow_versions
   WHERE workflow_id = OLD.id;

  INSERT INTO public.workflow_versions
    (workflow_id, version_number, title, description, sop_text, category, parsed_steps, created_by)
  VALUES
    (OLD.id, next_version, OLD.title, OLD.description, OLD.sop_text, OLD.category, OLD.parsed_steps, OLD.user_id);

  -- Purge versions beyond the most recent 10
  DELETE FROM public.workflow_versions
  WHERE workflow_id = OLD.id
    AND version_number <= (next_version - 10);

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_snapshot_workflow_version ON public.workflows;
CREATE TRIGGER trg_snapshot_workflow_version
  BEFORE UPDATE ON public.workflows
  FOR EACH ROW
  WHEN (
    OLD.title IS DISTINCT FROM NEW.title
    OR OLD.sop_text IS DISTINCT FROM NEW.sop_text
    OR OLD.description IS DISTINCT FROM NEW.description
    OR OLD.category IS DISTINCT FROM NEW.category
    OR OLD.parsed_steps IS DISTINCT FROM NEW.parsed_steps
  )
  EXECUTE FUNCTION public.snapshot_workflow_version();