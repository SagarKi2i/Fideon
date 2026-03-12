
-- Agent pipelines for configuring agent workflow chains
CREATE TABLE public.agent_pipelines (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  steps JSONB NOT NULL DEFAULT '[]'::jsonb,
  -- steps: [{ agent_id, agent_name, input_sources: [{type, config}], output_actions: [{type, config}] }]
  schedule_config JSONB,
  -- schedule_config: { enabled, type: 'recurring'|'one_time', cron_expression, scheduled_at }
  is_active BOOLEAN NOT NULL DEFAULT true,
  last_run_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.agent_pipelines ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own pipelines"
ON public.agent_pipelines FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can create own pipelines"
ON public.agent_pipelines FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own pipelines"
ON public.agent_pipelines FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own pipelines"
ON public.agent_pipelines FOR DELETE
USING (auth.uid() = user_id);

CREATE TRIGGER update_agent_pipelines_updated_at
BEFORE UPDATE ON public.agent_pipelines
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Visual workflow builder nodes/edges storage
CREATE TABLE public.visual_workflows (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
  edges JSONB NOT NULL DEFAULT '[]'::jsonb,
  is_active BOOLEAN NOT NULL DEFAULT true,
  last_run_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.visual_workflows ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own visual workflows"
ON public.visual_workflows FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can create own visual workflows"
ON public.visual_workflows FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own visual workflows"
ON public.visual_workflows FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own visual workflows"
ON public.visual_workflows FOR DELETE
USING (auth.uid() = user_id);

CREATE TRIGGER update_visual_workflows_updated_at
BEFORE UPDATE ON public.visual_workflows
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();
