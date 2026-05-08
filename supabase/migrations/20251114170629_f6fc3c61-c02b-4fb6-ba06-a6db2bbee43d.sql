-- Create devices table
CREATE TABLE public.devices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_name TEXT NOT NULL,
  device_token TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'never_checked_in' CHECK (status IN ('online', 'offline', 'never_checked_in')),
  os_type TEXT,
  app_version TEXT,
  last_seen_at TIMESTAMP WITH TIME ZONE,
  registered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  registered_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create device_models table for model assignments
CREATE TABLE public.device_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID NOT NULL REFERENCES public.devices(id) ON DELETE CASCADE,
  model_id TEXT NOT NULL,
  model_name TEXT NOT NULL,
  domain TEXT NOT NULL,
  allocated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  allocated_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  ollama_model_name TEXT,
  is_downloaded BOOLEAN DEFAULT false,
  last_synced_at TIMESTAMP WITH TIME ZONE,
  UNIQUE(device_id, model_id)
);

-- Create device_sync_logs table
CREATE TABLE public.device_sync_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID NOT NULL REFERENCES public.devices(id) ON DELETE CASCADE,
  sync_type TEXT NOT NULL CHECK (sync_type IN ('checkin', 'model_sync', 'config_update')),
  status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
  details JSONB,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create device_usage_logs table
CREATE TABLE public.device_usage_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID NOT NULL REFERENCES public.devices(id) ON DELETE CASCADE,
  model_id TEXT NOT NULL,
  prompt_count INTEGER DEFAULT 0,
  tokens_used INTEGER DEFAULT 0,
  duration_seconds INTEGER DEFAULT 0,
  logged_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create indexes for performance
CREATE INDEX idx_devices_status ON public.devices(status);
CREATE INDEX idx_devices_last_seen ON public.devices(last_seen_at DESC);
CREATE INDEX idx_device_models_device_id ON public.device_models(device_id);
CREATE INDEX idx_device_sync_logs_device_id ON public.device_sync_logs(device_id, created_at DESC);
CREATE INDEX idx_device_usage_logs_device_id ON public.device_usage_logs(device_id, logged_at DESC);

-- Enable RLS on all tables
ALTER TABLE public.devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.device_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.device_sync_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.device_usage_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policies - Only admins can manage devices
CREATE POLICY "Admins can view all devices"
  ON public.devices FOR SELECT
  USING (has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can insert devices"
  ON public.devices FOR INSERT
  WITH CHECK (has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can update devices"
  ON public.devices FOR UPDATE
  USING (has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can delete devices"
  ON public.devices FOR DELETE
  USING (has_role(auth.uid(), 'admin'));

-- Device models policies
CREATE POLICY "Admins can view device models"
  ON public.device_models FOR SELECT
  USING (has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can manage device models"
  ON public.device_models FOR ALL
  USING (has_role(auth.uid(), 'admin'));

-- Device sync logs policies
CREATE POLICY "Admins can view sync logs"
  ON public.device_sync_logs FOR SELECT
  USING (has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can insert sync logs"
  ON public.device_sync_logs FOR INSERT
  WITH CHECK (has_role(auth.uid(), 'admin'));

-- Device usage logs policies
CREATE POLICY "Admins can view usage logs"
  ON public.device_usage_logs FOR SELECT
  USING (has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can insert usage logs"
  ON public.device_usage_logs FOR INSERT
  WITH CHECK (has_role(auth.uid(), 'admin'));

-- Create trigger for updated_at
CREATE TRIGGER update_devices_updated_at
  BEFORE UPDATE ON public.devices
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- Function to generate secure device token
CREATE OR REPLACE FUNCTION public.generate_device_token()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  token TEXT;
BEGIN
  token := encode(gen_random_bytes(32), 'base64');
  token := replace(token, '/', '_');
  token := replace(token, '+', '-');
  RETURN token;
END;
$$;