-- Add license types enum
CREATE TYPE public.license_type AS ENUM ('standard', 'premium', 'model_based');

-- Add license status enum
CREATE TYPE public.license_status AS ENUM ('active', 'suspended', 'expired');

-- Create device licenses table
CREATE TABLE public.device_licenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID NOT NULL REFERENCES public.devices(id) ON DELETE CASCADE,
  license_type public.license_type NOT NULL DEFAULT 'standard',
  status public.license_status NOT NULL DEFAULT 'active',
  issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ,
  suspended_at TIMESTAMPTZ,
  issued_by UUID REFERENCES auth.users(id),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create model packs table
CREATE TABLE public.model_packs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  domain TEXT NOT NULL,
  models JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create audit logs table
CREATE TABLE public.audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  details JSONB,
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create device analytics table
CREATE TABLE public.device_analytics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID NOT NULL REFERENCES public.devices(id) ON DELETE CASCADE,
  model_id TEXT NOT NULL,
  query_count INTEGER NOT NULL DEFAULT 0,
  token_usage INTEGER NOT NULL DEFAULT 0,
  cpu_load_avg DECIMAL(5,2),
  gpu_load_avg DECIMAL(5,2),
  error_count INTEGER NOT NULL DEFAULT 0,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(device_id, model_id, date)
);

-- Add indexes
CREATE INDEX idx_device_licenses_device_id ON public.device_licenses(device_id);
CREATE INDEX idx_device_licenses_status ON public.device_licenses(status);
CREATE INDEX idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX idx_audit_logs_resource_type ON public.audit_logs(resource_type);
CREATE INDEX idx_audit_logs_created_at ON public.audit_logs(created_at DESC);
CREATE INDEX idx_device_analytics_device_id ON public.device_analytics(device_id);
CREATE INDEX idx_device_analytics_date ON public.device_analytics(date DESC);

-- Enable RLS
ALTER TABLE public.device_licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_packs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.device_analytics ENABLE ROW LEVEL SECURITY;

-- RLS Policies for device_licenses
CREATE POLICY "Admins can manage licenses"
  ON public.device_licenses
  FOR ALL
  USING (has_role(auth.uid(), 'admin'));

CREATE POLICY "Users can view licenses"
  ON public.device_licenses
  FOR SELECT
  USING (true);

-- RLS Policies for model_packs
CREATE POLICY "Admins can manage model packs"
  ON public.model_packs
  FOR ALL
  USING (has_role(auth.uid(), 'admin'));

CREATE POLICY "Users can view model packs"
  ON public.model_packs
  FOR SELECT
  USING (true);

-- RLS Policies for audit_logs
CREATE POLICY "Admins can view all audit logs"
  ON public.audit_logs
  FOR SELECT
  USING (has_role(auth.uid(), 'admin'));

CREATE POLICY "Users can view their own audit logs"
  ON public.audit_logs
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "System can insert audit logs"
  ON public.audit_logs
  FOR INSERT
  WITH CHECK (true);

-- RLS Policies for device_analytics
CREATE POLICY "Admins can view all analytics"
  ON public.device_analytics
  FOR SELECT
  USING (has_role(auth.uid(), 'admin'));

CREATE POLICY "Users can view analytics"
  ON public.device_analytics
  FOR SELECT
  USING (true);

CREATE POLICY "System can insert analytics"
  ON public.device_analytics
  FOR INSERT
  WITH CHECK (true);

-- Add trigger for updated_at on device_licenses
CREATE TRIGGER update_device_licenses_updated_at
  BEFORE UPDATE ON public.device_licenses
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- Add trigger for updated_at on model_packs
CREATE TRIGGER update_model_packs_updated_at
  BEFORE UPDATE ON public.model_packs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();