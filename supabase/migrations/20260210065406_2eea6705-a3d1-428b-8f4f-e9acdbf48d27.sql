
-- Create table for scheduled agent runs
CREATE TABLE public.agent_schedules (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  model_id TEXT NOT NULL,
  model_name TEXT NOT NULL,
  schedule_type TEXT NOT NULL CHECK (schedule_type IN ('one_time', 'recurring')),
  cron_expression TEXT, -- e.g. '0 9 * * 1' for every Monday at 9am
  scheduled_at TIMESTAMPTZ, -- for one_time schedules
  prompt TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  last_run_at TIMESTAMPTZ,
  next_run_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.agent_schedules ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own schedules"
ON public.agent_schedules FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own schedules"
ON public.agent_schedules FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own schedules"
ON public.agent_schedules FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own schedules"
ON public.agent_schedules FOR DELETE
USING (auth.uid() = user_id);

-- Timestamp trigger
CREATE TRIGGER update_agent_schedules_updated_at
BEFORE UPDATE ON public.agent_schedules
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();
