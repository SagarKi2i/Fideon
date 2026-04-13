-- ============================================================================
-- GENERATED FILE - DO NOT EDIT BY HAND
-- ============================================================================
-- Source: supabase/migrations
-- Generated: 2026-04-10 17:19:03+05:30
--
-- This file is a concatenation of all SQL files in supabase/migrations.
-- Ordering:
--   1) Files starting with a timestamp prefix like 20260408090000_*.sql (ASC)
--   2) Any remaining *.sql files (ASC by name)
--
-- Notes for Supabase SQL editor:
-- - Run as a single script on a clean public schema (recommended: DROP SCHEMA public CASCADE;
--   then CREATE SCHEMA public; restore USAGE/CREATE grants for postgres, anon, authenticated, service_role).
-- - storage.* objects are not dropped by public reset; migrations use DROP POLICY IF EXISTS on storage.objects
--   where policies are created.
-- - Optional: TRUNCATE supabase_migrations.schema_migrations; if you use Supabase migration history.
-- - Excluded from this bundle (by build script): Extraction To Fine-Tuning Data Migration.sql
--   (duplicate bootstrap; same content is covered by timestamped migrations).
-- - After 20260312210000_role_expansion_signup.sql the bundle inserts COMMIT; so new app_role enum
--   labels are visible (PostgreSQL: new enum values cannot be used in the same transaction as ADD VALUE).
-- - Optional manual seed (NOT in this file): supabase/seed_bootstrap_global_admin.sql
-- ============================================================================
-- ============================================================================
-- BEGIN MIGRATION: 20251114050518_1fe14af7-829e-463e-b229-e380f19f8747.sql
-- ============================================================================
-- Create enum for model domains
CREATE TYPE model_domain AS ENUM ('insurance', 'healthcare', 'banking', 'legal', 'travel');

-- Create enum for model providers
CREATE TYPE model_provider AS ENUM ('ollama', 'lmstudio', 'openai', 'custom');

-- Table for activated models
CREATE TABLE public.activated_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  model_id TEXT NOT NULL,
  model_name TEXT NOT NULL,
  domain model_domain NOT NULL,
  activated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, model_id)
);

-- Table for custom model endpoints
CREATE TABLE public.model_endpoints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  endpoint_url TEXT NOT NULL,
  provider model_provider NOT NULL,
  temperature DECIMAL(3,2) DEFAULT 0.7,
  max_tokens INTEGER DEFAULT 2048,
  system_prompt TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for documents
CREATE TABLE public.documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  file_type TEXT NOT NULL,
  file_size BIGINT NOT NULL,
  storage_path TEXT NOT NULL,
  uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for chat conversations
CREATE TABLE public.chat_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  model_id TEXT,
  title TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for chat messages
CREATE TABLE public.chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES public.chat_conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for policy comparisons
CREATE TABLE public.policy_comparisons (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  policy_a_document_id UUID REFERENCES public.documents(id) ON DELETE CASCADE,
  policy_b_document_id UUID REFERENCES public.documents(id) ON DELETE CASCADE,
  comparison_result JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.activated_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_endpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policy_comparisons ENABLE ROW LEVEL SECURITY;

-- RLS Policies for activated_models
CREATE POLICY "Users can view their own activated models"
  ON public.activated_models FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can activate models"
  ON public.activated_models FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can deactivate their own models"
  ON public.activated_models FOR DELETE
  USING (auth.uid() = user_id);

-- RLS Policies for model_endpoints
CREATE POLICY "Users can view their own endpoints"
  ON public.model_endpoints FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create endpoints"
  ON public.model_endpoints FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own endpoints"
  ON public.model_endpoints FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own endpoints"
  ON public.model_endpoints FOR DELETE
  USING (auth.uid() = user_id);

-- RLS Policies for documents
CREATE POLICY "Users can view their own documents"
  ON public.documents FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can upload documents"
  ON public.documents FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own documents"
  ON public.documents FOR DELETE
  USING (auth.uid() = user_id);

-- RLS Policies for chat_conversations
CREATE POLICY "Users can view their own conversations"
  ON public.chat_conversations FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create conversations"
  ON public.chat_conversations FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own conversations"
  ON public.chat_conversations FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own conversations"
  ON public.chat_conversations FOR DELETE
  USING (auth.uid() = user_id);

-- RLS Policies for chat_messages
CREATE POLICY "Users can view messages in their conversations"
  ON public.chat_messages FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM public.chat_conversations
    WHERE id = chat_messages.conversation_id
    AND user_id = auth.uid()
  ));

CREATE POLICY "Users can create messages in their conversations"
  ON public.chat_messages FOR INSERT
  WITH CHECK (EXISTS (
    SELECT 1 FROM public.chat_conversations
    WHERE id = chat_messages.conversation_id
    AND user_id = auth.uid()
  ));

-- RLS Policies for policy_comparisons
CREATE POLICY "Users can view their own comparisons"
  ON public.policy_comparisons FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create comparisons"
  ON public.policy_comparisons FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own comparisons"
  ON public.policy_comparisons FOR DELETE
  USING (auth.uid() = user_id);

-- Create storage bucket for documents
-- Your VM's storage schema does not include a `public` column on `storage.buckets`
-- (it has: id, name, owner, created_at, updated_at). Insert bucket without owner/public.
INSERT INTO storage.buckets (id, name)
VALUES ('documents', 'documents')
ON CONFLICT (id) DO NOTHING;

-- Storage policies for documents bucket (idempotent if policies already exist)
DROP POLICY IF EXISTS "Users can upload their own documents" ON storage.objects;
DROP POLICY IF EXISTS "Users can view their own documents" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete their own documents" ON storage.objects;

CREATE POLICY "Users can upload their own documents"
  ON storage.objects FOR INSERT
  WITH CHECK (
    bucket_id = 'documents' AND
    auth.uid()::text = (storage.foldername(name))[1]
  );

CREATE POLICY "Users can view their own documents"
  ON storage.objects FOR SELECT
  USING (
    bucket_id = 'documents' AND
    auth.uid()::text = (storage.foldername(name))[1]
  );

CREATE POLICY "Users can delete their own documents"
  ON storage.objects FOR DELETE
  USING (
    bucket_id = 'documents' AND
    auth.uid()::text = (storage.foldername(name))[1]
  );

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_model_endpoints_updated_at
  BEFORE UPDATE ON public.model_endpoints
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_conversations_updated_at
  BEFORE UPDATE ON public.chat_conversations
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- END MIGRATION: 20251114050518_1fe14af7-829e-463e-b229-e380f19f8747.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20251114050640_5a1101c0-ba24-4e29-9d37-77a9c7a1684d.sql
-- ============================================================================
-- Fix function search path security issue by recreating triggers
DROP TRIGGER IF EXISTS update_model_endpoints_updated_at ON public.model_endpoints;
DROP TRIGGER IF EXISTS update_chat_conversations_updated_at ON public.chat_conversations;
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Recreate function with proper search_path
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public;

-- Recreate triggers
CREATE TRIGGER update_model_endpoints_updated_at
  BEFORE UPDATE ON public.model_endpoints
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_conversations_updated_at
  BEFORE UPDATE ON public.chat_conversations
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- END MIGRATION: 20251114050640_5a1101c0-ba24-4e29-9d37-77a9c7a1684d.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20251114065305_f571d454-0932-4a50-8c28-408cdb6f24db.sql
-- ============================================================================
-- Create role enum
CREATE TYPE public.app_role AS ENUM ('admin', 'user');

-- Create user_roles table
CREATE TABLE public.user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  role app_role NOT NULL DEFAULT 'user',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  UNIQUE(user_id, role)
);

-- Enable RLS
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

-- Create security definer function to check roles
CREATE OR REPLACE FUNCTION public.has_role(_user_id UUID, _role app_role)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.user_roles
    WHERE user_id = _user_id
      AND role = _role
  )
$$;

-- RLS policies for user_roles
CREATE POLICY "Users can view their own roles"
  ON public.user_roles
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Admins can manage all roles"
  ON public.user_roles
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'));

-- Insert default user role for existing users
INSERT INTO public.user_roles (user_id, role)
SELECT id, 'user'::app_role
FROM auth.users
ON CONFLICT (user_id, role) DO NOTHING;

-- ============================================================================
-- END MIGRATION: 20251114065305_f571d454-0932-4a50-8c28-408cdb6f24db.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20251114170629_f6fc3c61-c02b-4fb6-ba06-a6db2bbee43d.sql
-- ============================================================================
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

-- ============================================================================
-- END MIGRATION: 20251114170629_f6fc3c61-c02b-4fb6-ba06-a6db2bbee43d.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20251114170705_3f2d990a-81e8-45e5-89e4-b778f6590403.sql
-- ============================================================================
-- Fix search_path for generate_device_token function
CREATE OR REPLACE FUNCTION public.generate_device_token()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
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

-- ============================================================================
-- END MIGRATION: 20251114170705_3f2d990a-81e8-45e5-89e4-b778f6590403.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20251114172014_eb6738e9-7683-4ff6-a058-b2dcbece6625.sql
-- ============================================================================
-- Enable pgcrypto extension for secure random token generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================================
-- END MIGRATION: 20251114172014_eb6738e9-7683-4ff6-a058-b2dcbece6625.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20251114172202_dbf548c0-6c65-48c3-a548-b8c5bd8e1de8.sql
-- ============================================================================
-- Fix generate_device_token to work with restricted search_path by qualifying pgcrypto function
CREATE OR REPLACE FUNCTION public.generate_device_token()
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  token TEXT;
BEGIN
  -- Use the pgcrypto function from the extensions schema explicitly
  token := encode(extensions.gen_random_bytes(32), 'base64');
  token := replace(token, '/', '_');
  token := replace(token, '+', '-');
  RETURN token;
END;
$$;

-- ============================================================================
-- END MIGRATION: 20251114172202_dbf548c0-6c65-48c3-a548-b8c5bd8e1de8.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20251114172237_50504f12-f31a-4a1c-a962-14f24c7ba429.sql
-- ============================================================================
-- Fix generate_device_token to work with restricted search_path by qualifying pgcrypto function
CREATE OR REPLACE FUNCTION public.generate_device_token()
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  token TEXT;
BEGIN
  -- Use the pgcrypto function from the extensions schema explicitly
  token := encode(extensions.gen_random_bytes(32), 'base64');
  token := replace(token, '/', '_');
  token := replace(token, '+', '-');
  RETURN token;
END;
$$;

-- ============================================================================
-- END MIGRATION: 20251114172237_50504f12-f31a-4a1c-a962-14f24c7ba429.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20251116145514_03b8c065-31f2-46c1-a062-a1f2e4363a04.sql
-- ============================================================================
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

-- ============================================================================
-- END MIGRATION: 20251116145514_03b8c065-31f2-46c1-a062-a1f2e4363a04.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20251118064832_233c0fff-c47b-42f7-8cbd-785c6a68f214.sql
-- ============================================================================
-- Add unique constraint to user_roles to prevent duplicate roles per user
ALTER TABLE user_roles ADD CONSTRAINT user_roles_user_id_unique UNIQUE (user_id);

-- ============================================================================
-- END MIGRATION: 20251118064832_233c0fff-c47b-42f7-8cbd-785c6a68f214.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260209160128_0b21f322-67e0-4894-a10a-a39dcd8e8bde.sql
-- ============================================================================

-- Training feedback collected from users on AI outputs
CREATE TABLE public.training_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid REFERENCES public.devices(id) ON DELETE CASCADE NOT NULL,
  model_id text NOT NULL,
  prompt text NOT NULL,
  original_response text NOT NULL,
  corrected_response text,
  rating integer CHECK (rating >= 1 AND rating <= 5),
  feedback_type text NOT NULL DEFAULT 'correction', -- correction, rating, thumbs
  metadata jsonb DEFAULT '{}'::jsonb,
  is_used_for_training boolean DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.training_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Device functions can insert feedback"
  ON public.training_feedback FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Admins can view all feedback"
  ON public.training_feedback FOR SELECT
  USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can update feedback"
  ON public.training_feedback FOR UPDATE
  USING (has_role(auth.uid(), 'admin'::app_role));

-- Local training jobs run on devices
CREATE TABLE public.training_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid REFERENCES public.devices(id) ON DELETE CASCADE NOT NULL,
  model_id text NOT NULL,
  status text NOT NULL DEFAULT 'pending', -- pending, running, completed, failed
  training_type text NOT NULL DEFAULT 'lora', -- lora, modelfile, full
  config jsonb DEFAULT '{}'::jsonb,
  metrics jsonb DEFAULT '{}'::jsonb, -- loss, accuracy, epochs
  feedback_count integer DEFAULT 0,
  started_at timestamptz,
  completed_at timestamptz,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.training_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Device functions can manage training jobs"
  ON public.training_jobs FOR ALL
  USING (true);

CREATE POLICY "Admins can view all training jobs"
  ON public.training_jobs FOR SELECT
  USING (has_role(auth.uid(), 'admin'::app_role));

-- Federated model updates (gradient deltas from devices)
CREATE TABLE public.federated_updates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid REFERENCES public.devices(id) ON DELETE CASCADE NOT NULL,
  model_id text NOT NULL,
  round_number integer NOT NULL DEFAULT 1,
  gradient_hash text NOT NULL, -- hash of gradient delta for integrity
  gradient_size_bytes bigint DEFAULT 0,
  storage_path text, -- path in storage bucket
  metrics jsonb DEFAULT '{}'::jsonb, -- local training metrics
  status text NOT NULL DEFAULT 'pending', -- pending, accepted, rejected, aggregated
  privacy_noise_added boolean DEFAULT true,
  submitted_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.federated_updates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Device functions can insert updates"
  ON public.federated_updates FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Admins can manage federated updates"
  ON public.federated_updates FOR ALL
  USING (has_role(auth.uid(), 'admin'::app_role));

-- Federated rounds tracking
CREATE TABLE public.federated_rounds (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id text NOT NULL,
  round_number integer NOT NULL,
  status text NOT NULL DEFAULT 'collecting', -- collecting, aggregating, completed, distributed
  min_participants integer DEFAULT 3,
  current_participants integer DEFAULT 0,
  aggregated_model_path text,
  aggregation_method text DEFAULT 'fedavg', -- fedavg, fedprox, scaffold
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  distributed_at timestamptz,
  metrics jsonb DEFAULT '{}'::jsonb
);

ALTER TABLE public.federated_rounds ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage rounds"
  ON public.federated_rounds FOR ALL
  USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Devices can view active rounds"
  ON public.federated_rounds FOR SELECT
  USING (true);

-- Storage bucket for gradient deltas
-- Your VM's storage.buckets does not have a `public` column (it has: id, name, owner, created_at, updated_at).
-- Insert bucket without public/owner.
INSERT INTO storage.buckets (id, name)
VALUES ('model-updates', 'model-updates')
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Devices can upload gradients" ON storage.objects;
DROP POLICY IF EXISTS "Admins can view gradients" ON storage.objects;

CREATE POLICY "Devices can upload gradients"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'model-updates');

CREATE POLICY "Admins can view gradients"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'model-updates' AND has_role(auth.uid(), 'admin'::app_role));

-- ============================================================================
-- END MIGRATION: 20260209160128_0b21f322-67e0-4894-a10a-a39dcd8e8bde.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260209160158_2ec3a1aa-6eaa-4430-bf4a-349dc5721b79.sql
-- ============================================================================

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

-- ============================================================================
-- END MIGRATION: 20260209160158_2ec3a1aa-6eaa-4430-bf4a-349dc5721b79.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260209162615_832e6a30-56f3-4021-b80a-4f646114819d.sql
-- ============================================================================

-- Create workflows table for custom SOPs
CREATE TABLE public.workflows (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  sop_text TEXT NOT NULL,
  category TEXT DEFAULT 'general',
  parsed_steps JSONB DEFAULT '[]'::jsonb,
  is_template BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create workflow runs table to track executions
CREATE TABLE public.workflow_runs (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  workflow_id UUID NOT NULL REFERENCES public.workflows(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  status TEXT NOT NULL DEFAULT 'in_progress',
  current_step INTEGER DEFAULT 0,
  step_results JSONB DEFAULT '[]'::jsonb,
  started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  completed_at TIMESTAMP WITH TIME ZONE
);

-- Enable RLS
ALTER TABLE public.workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_runs ENABLE ROW LEVEL SECURITY;

-- Workflows: users see their own + templates
CREATE POLICY "Users can view own workflows and templates"
  ON public.workflows FOR SELECT
  USING (auth.uid() = user_id OR is_template = true);

CREATE POLICY "Users can create their own workflows"
  ON public.workflows FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own workflows"
  ON public.workflows FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own workflows"
  ON public.workflows FOR DELETE
  USING (auth.uid() = user_id);

-- Workflow runs: users see their own
CREATE POLICY "Users can view own runs"
  ON public.workflow_runs FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create own runs"
  ON public.workflow_runs FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own runs"
  ON public.workflow_runs FOR UPDATE
  USING (auth.uid() = user_id);

-- Timestamp trigger
CREATE TRIGGER update_workflows_updated_at
  BEFORE UPDATE ON public.workflows
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- END MIGRATION: 20260209162615_832e6a30-56f3-4021-b80a-4f646114819d.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260210065406_2eea6705-a3d1-428b-8f4f-e9acdbf48d27.sql
-- ============================================================================

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

-- ============================================================================
-- END MIGRATION: 20260210065406_2eea6705-a3d1-428b-8f4f-e9acdbf48d27.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260210070044_68c3b314-abb2-4209-90c1-cbd036753e23.sql
-- ============================================================================

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

-- ============================================================================
-- END MIGRATION: 20260210070044_68c3b314-abb2-4209-90c1-cbd036753e23.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260211105451_e1ad5a4d-556c-4343-8b30-1508a0fcba5c.sql
-- ============================================================================
-- Allow admins to view all activated models
CREATE POLICY "Admins can view all activated models"
ON public.activated_models
FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

-- Allow admins to insert activated models for any user
CREATE POLICY "Admins can allocate models to users"
ON public.activated_models
FOR INSERT
WITH CHECK (has_role(auth.uid(), 'admin'::app_role));

-- Allow admins to delete activated models for any user
CREATE POLICY "Admins can deallocate models from users"
ON public.activated_models
FOR DELETE
USING (has_role(auth.uid(), 'admin'::app_role));

-- ============================================================================
-- END MIGRATION: 20260211105451_e1ad5a4d-556c-4343-8b30-1508a0fcba5c.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260211111000_8359461f-7f50-44a4-a6a1-f6c8c2de1815.sql
-- ============================================================================

-- Create pod activation requests table
CREATE TABLE public.pod_activation_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  model_id text NOT NULL,
  model_name text NOT NULL,
  domain text NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  requested_at timestamp with time zone NOT NULL DEFAULT now(),
  reviewed_at timestamp with time zone,
  reviewed_by uuid,
  rejection_reason text,
  UNIQUE(user_id, model_id, status)
);

-- Enable RLS
ALTER TABLE public.pod_activation_requests ENABLE ROW LEVEL SECURITY;

-- Users can create requests
CREATE POLICY "Users can create activation requests"
ON public.pod_activation_requests FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- Users can view their own requests
CREATE POLICY "Users can view their own requests"
ON public.pod_activation_requests FOR SELECT
USING (auth.uid() = user_id);

-- Admins can view all requests
CREATE POLICY "Admins can view all requests"
ON public.pod_activation_requests FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

-- Admins can update requests (approve/reject)
CREATE POLICY "Admins can update requests"
ON public.pod_activation_requests FOR UPDATE
USING (has_role(auth.uid(), 'admin'::app_role));

-- Users can delete their own pending requests
CREATE POLICY "Users can cancel pending requests"
ON public.pod_activation_requests FOR DELETE
USING (auth.uid() = user_id AND status = 'pending');

-- ============================================================================
-- END MIGRATION: 20260211111000_8359461f-7f50-44a4-a6a1-f6c8c2de1815.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260221071603_6b8fef50-81aa-42c0-9394-23b7bf9729d4.sql
-- ============================================================================

-- Decision Review Queue table for human-in-the-loop across all pods
CREATE TABLE public.decision_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  pod_model_id text NOT NULL,
  pod_model_name text NOT NULL,
  domain text NOT NULL,
  decision_type text NOT NULL, -- e.g. 'quote_approval', 'claim_decision', 'submission_triage'
  title text NOT NULL,
  summary text,
  ai_recommendation text,
  confidence_score numeric,
  threshold_exceeded boolean DEFAULT true,
  input_data jsonb DEFAULT '{}'::jsonb,
  output_data jsonb DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending', -- pending, approved, rejected
  reviewer_id uuid,
  reviewer_notes text,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.decision_reviews ENABLE ROW LEVEL SECURITY;

-- Users can view their own decisions
CREATE POLICY "Users can view their own reviews"
ON public.decision_reviews FOR SELECT
USING (auth.uid() = user_id);

-- Users can create review requests
CREATE POLICY "Users can create reviews"
ON public.decision_reviews FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- Admins can view all reviews
CREATE POLICY "Admins can view all reviews"
ON public.decision_reviews FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

-- Admins can update reviews (approve/reject)
CREATE POLICY "Admins can update reviews"
ON public.decision_reviews FOR UPDATE
USING (has_role(auth.uid(), 'admin'::app_role));

-- Users can update their own pending reviews (e.g. cancel)
CREATE POLICY "Users can update own pending reviews"
ON public.decision_reviews FOR UPDATE
USING (auth.uid() = user_id AND status = 'pending');

-- Trigger for updated_at
CREATE TRIGGER update_decision_reviews_updated_at
BEFORE UPDATE ON public.decision_reviews
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- END MIGRATION: 20260221071603_6b8fef50-81aa-42c0-9394-23b7bf9729d4.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260312131500_auto_user_role_on_signup.sql
-- ============================================================================
-- Ensure every auth user has a default role row in public.user_roles

-- Backfill missing role rows for existing users
INSERT INTO public.user_roles (user_id, role)
SELECT u.id, 'user'::public.app_role
FROM auth.users u
LEFT JOIN public.user_roles r ON r.user_id = u.id
WHERE r.user_id IS NULL;

-- Trigger function to create role row for new users
CREATE OR REPLACE FUNCTION public.handle_new_user_role()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, 'user'::public.app_role)
  ON CONFLICT (user_id) DO NOTHING;

  RETURN NEW;
END;
$$;

-- Recreate trigger safely
DROP TRIGGER IF EXISTS on_auth_user_created_set_role ON auth.users;

CREATE TRIGGER on_auth_user_created_set_role
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.handle_new_user_role();

-- ============================================================================
-- END MIGRATION: 20260312131500_auto_user_role_on_signup.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260312193000_fnf9_schema_closure.sql
-- ============================================================================
-- Sprint-1 schema closure (backward compatible)
-- Adds users/roles/tenants/model catalog entities without breaking current auth+RBAC flow.

-- Tenants
CREATE TABLE IF NOT EXISTS public.tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Role metadata (keeps existing public.user_roles as assignment table)
CREATE TABLE IF NOT EXISTS public.roles (
  role public.app_role PRIMARY KEY,
  display_name TEXT NOT NULL,
  description TEXT,
  permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO public.roles (role, display_name, description, permissions)
VALUES
  ('admin', 'Administrator', 'Full tenant administration access', '["*"]'::jsonb),
  ('user', 'Standard User', 'Standard application access', '["dashboard.read","models.use"]'::jsonb)
ON CONFLICT (role) DO UPDATE
SET
  display_name = EXCLUDED.display_name,
  description = EXCLUDED.description;

-- Auth-linked app users profile table
CREATE TABLE IF NOT EXISTS public.app_users (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  full_name TEXT,
  tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
  last_login_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_users_tenant_id ON public.app_users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_app_users_email ON public.app_users(email);

-- Model catalog table for story-level model inventory requirements
CREATE TABLE IF NOT EXISTS public.model_catalog (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id TEXT NOT NULL UNIQUE,
  model_name TEXT NOT NULL,
  domain TEXT NOT NULL,
  provider TEXT NOT NULL,
  description TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_catalog_domain ON public.model_catalog(domain);
CREATE INDEX IF NOT EXISTS idx_model_catalog_active ON public.model_catalog(is_active);

-- Ensure a default tenant exists
INSERT INTO public.tenants (slug, name, is_active)
VALUES ('default-tenant', 'Default Tenant', true)
ON CONFLICT (slug) DO NOTHING;

-- Backfill app_users for existing auth users
WITH default_tenant AS (
  SELECT id FROM public.tenants WHERE slug = 'default-tenant' LIMIT 1
)
INSERT INTO public.app_users (user_id, email, tenant_id, status)
SELECT
  u.id,
  COALESCE(u.email, ''),
  (SELECT id FROM default_tenant),
  'active'
FROM auth.users u
LEFT JOIN public.app_users au ON au.user_id = u.id
WHERE au.user_id IS NULL;

-- Keep app_users in sync when new auth users are created
CREATE OR REPLACE FUNCTION public.handle_new_app_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  default_tenant_id UUID;
BEGIN
  SELECT id INTO default_tenant_id
  FROM public.tenants
  WHERE slug = 'default-tenant'
  LIMIT 1;

  INSERT INTO public.app_users (user_id, email, tenant_id, status)
  VALUES (NEW.id, COALESCE(NEW.email, ''), default_tenant_id, 'active')
  ON CONFLICT (user_id) DO NOTHING;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created_set_profile ON auth.users;

CREATE TRIGGER on_auth_user_created_set_profile
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.handle_new_app_user();

-- Updated_at triggers
DROP TRIGGER IF EXISTS update_tenants_updated_at ON public.tenants;
CREATE TRIGGER update_tenants_updated_at
  BEFORE UPDATE ON public.tenants
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_roles_updated_at ON public.roles;
CREATE TRIGGER update_roles_updated_at
  BEFORE UPDATE ON public.roles
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_app_users_updated_at ON public.app_users;
CREATE TRIGGER update_app_users_updated_at
  BEFORE UPDATE ON public.app_users
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_model_catalog_updated_at ON public.model_catalog;
CREATE TRIGGER update_model_catalog_updated_at
  BEFORE UPDATE ON public.model_catalog
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- END MIGRATION: 20260312193000_fnf9_schema_closure.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260312194000_fnf10_rls_hardening.sql
-- ============================================================================
-- Sprint-1 RLS closure on current role-based architecture

-- New schema entities
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.app_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_catalog ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own app profile" ON public.app_users;
CREATE POLICY "Users can view own app profile"
  ON public.app_users
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own app profile" ON public.app_users;
CREATE POLICY "Users can update own app profile"
  ON public.app_users
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Admins can view all app users" ON public.app_users;
CREATE POLICY "Admins can view all app users"
  ON public.app_users
  FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Admins can manage app users" ON public.app_users;
CREATE POLICY "Admins can manage app users"
  ON public.app_users
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Authenticated users can view role metadata" ON public.roles;
CREATE POLICY "Authenticated users can view role metadata"
  ON public.roles
  FOR SELECT
  USING (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS "Admins can manage role metadata" ON public.roles;
CREATE POLICY "Admins can manage role metadata"
  ON public.roles
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Users can view own tenant" ON public.tenants;
CREATE POLICY "Users can view own tenant"
  ON public.tenants
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1
      FROM public.app_users au
      WHERE au.user_id = auth.uid()
        AND au.tenant_id = tenants.id
    )
  );

DROP POLICY IF EXISTS "Admins can manage all tenants" ON public.tenants;
CREATE POLICY "Admins can manage all tenants"
  ON public.tenants
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Authenticated users can view model catalog" ON public.model_catalog;
CREATE POLICY "Authenticated users can view model catalog"
  ON public.model_catalog
  FOR SELECT
  USING (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS "Admins can manage model catalog" ON public.model_catalog;
CREATE POLICY "Admins can manage model catalog"
  ON public.model_catalog
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- Normalize user_roles policies (explicit by operation)
DROP POLICY IF EXISTS "Users can view their own roles" ON public.user_roles;
DROP POLICY IF EXISTS "Admins can manage all roles" ON public.user_roles;

CREATE POLICY "Users can view their own roles"
  ON public.user_roles
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all user roles"
  ON public.user_roles
  FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can insert user roles"
  ON public.user_roles
  FOR INSERT
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can update user roles"
  ON public.user_roles
  FOR UPDATE
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can delete user roles"
  ON public.user_roles
  FOR DELETE
  USING (public.has_role(auth.uid(), 'admin'));

-- Normalize devices policies
DROP POLICY IF EXISTS "Admins can view all devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can insert devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can update devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can delete devices" ON public.devices;

CREATE POLICY "Admins can view all devices"
  ON public.devices FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can insert devices"
  ON public.devices FOR INSERT
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can update devices"
  ON public.devices FOR UPDATE
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can delete devices"
  ON public.devices FOR DELETE
  USING (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Admins can view device models" ON public.device_models;
DROP POLICY IF EXISTS "Admins can manage device models" ON public.device_models;

CREATE POLICY "Admins can view device models"
  ON public.device_models FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can insert device models"
  ON public.device_models FOR INSERT
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can update device models"
  ON public.device_models FOR UPDATE
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can delete device models"
  ON public.device_models FOR DELETE
  USING (public.has_role(auth.uid(), 'admin'));

-- Normalize audit log policies
DROP POLICY IF EXISTS "Admins can view all audit logs" ON public.audit_logs;
DROP POLICY IF EXISTS "Users can view their own audit logs" ON public.audit_logs;
DROP POLICY IF EXISTS "System can insert audit logs" ON public.audit_logs;

CREATE POLICY "Admins can view all audit logs"
  ON public.audit_logs
  FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Users can view own audit logs"
  ON public.audit_logs
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Authenticated users can insert own audit logs"
  ON public.audit_logs
  FOR INSERT
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND (
      user_id IS NULL
      OR user_id = auth.uid()
      OR public.has_role(auth.uid(), 'admin')
    )
  );

-- ============================================================================
-- END MIGRATION: 20260312194000_fnf10_rls_hardening.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260312210000_role_expansion_signup.sql
-- ============================================================================
-- Expand role enum values first in isolated migration.

ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'global_admin';
ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'viewer';
ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'guest';

-- ============================================================================
-- END MIGRATION: 20260312210000_role_expansion_signup.sql
-- ============================================================================

-- ---------------------------------------------------------------------------
-- BUNDLE ONLY: commit so new app_role enum values are usable in statements below.
-- ---------------------------------------------------------------------------
COMMIT;

-- ============================================================================
-- BEGIN MIGRATION: 20260312211000_role_expansion_signup_followup.sql
-- ============================================================================
-- Follow-up migration after enum expansion.
-- When run via Supabase CLI, the prior file commits before this file runs.
-- When run from a single concatenated script, the bundle inserts COMMIT after the ADD VALUE migration.

-- Allow global_admin to pass admin checks used across RLS and backend access checks.
-- Compare global_admin via role::text so we never rely on a not-yet-committed enum label in one xact.
CREATE OR REPLACE FUNCTION public.has_role(_user_id UUID, _role app_role)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.user_roles
    WHERE user_id = _user_id
      AND (
        role = _role
        OR (_role = 'admin'::app_role AND role::text = 'global_admin')
      )
  )
$$;

-- Role rows for metadata table
INSERT INTO public.roles (role, display_name, description, permissions)
VALUES
  ('global_admin', 'Global Admin', 'Highest level administrative access', '["*"]'::jsonb),
  ('admin', 'Admin', 'Administrative access within tenant', '["dashboard.*","users.manage","devices.manage"]'::jsonb),
  ('user', 'User', 'Standard application user', '["dashboard.read","pods.use"]'::jsonb),
  ('viewer', 'Viewer', 'Read-only visibility', '["dashboard.read","reports.read"]'::jsonb),
  ('guest', 'Guest', 'Limited guest access', '["dashboard.read.limited"]'::jsonb)
ON CONFLICT (role) DO UPDATE
SET
  display_name = EXCLUDED.display_name,
  description = EXCLUDED.description;

-- Use signup metadata for role assignment.
CREATE OR REPLACE FUNCTION public.handle_new_user_role()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  requested_role TEXT;
  resolved_role public.app_role;
BEGIN
  requested_role := COALESCE(NEW.raw_user_meta_data ->> 'requested_role', 'user');

  resolved_role := CASE requested_role
    WHEN 'global_admin' THEN 'global_admin'::public.app_role
    WHEN 'admin' THEN 'admin'::public.app_role
    WHEN 'viewer' THEN 'viewer'::public.app_role
    WHEN 'guest' THEN 'guest'::public.app_role
    ELSE 'user'::public.app_role
  END;

  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, resolved_role)
  ON CONFLICT (user_id) DO UPDATE
  SET role = EXCLUDED.role;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created_set_role ON auth.users;
CREATE TRIGGER on_auth_user_created_set_role
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.handle_new_user_role();

-- Store signup full_name in app_users profile.
CREATE OR REPLACE FUNCTION public.handle_new_app_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  default_tenant_id UUID;
BEGIN
  SELECT id INTO default_tenant_id
  FROM public.tenants
  WHERE slug = 'default-tenant'
  LIMIT 1;

  INSERT INTO public.app_users (user_id, email, full_name, tenant_id, status)
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    NULLIF(NEW.raw_user_meta_data ->> 'full_name', ''),
    default_tenant_id,
    'active'
  )
  ON CONFLICT (user_id) DO UPDATE
  SET
    email = EXCLUDED.email,
    full_name = COALESCE(EXCLUDED.full_name, public.app_users.full_name);

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created_set_profile ON auth.users;
CREATE TRIGGER on_auth_user_created_set_profile
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.handle_new_app_user();

-- ============================================================================
-- END MIGRATION: 20260312211000_role_expansion_signup_followup.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260312233000_signup_onboarding_persistence.sql
-- ============================================================================
-- Persist full onboarding metadata from auth signup into application tables.
-- This migration extends the existing auth.users -> app_users trigger logic.

CREATE OR REPLACE FUNCTION public.handle_new_app_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  default_tenant_id UUID;
  resolved_tenant_id UUID;
  requested_tenant_name TEXT;
  requested_plan TEXT;
  requested_model_id TEXT;
  requested_device_name TEXT;
  normalized_slug TEXT;
  generated_slug TEXT;
  resolved_model_name TEXT;
  resolved_domain public.model_domain;
BEGIN
  -- Metadata sent from signup wizard
  requested_tenant_name := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'tenant_name', '')), '');
  requested_plan := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'plan', '')), '');
  requested_model_id := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'default_model_id', '')), '');
  requested_device_name := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'device_name', '')), '');

  SELECT id INTO default_tenant_id
  FROM public.tenants
  WHERE slug = 'default-tenant'
  LIMIT 1;

  resolved_tenant_id := default_tenant_id;

  -- Create a tenant for the user when tenant_name is provided.
  IF requested_tenant_name IS NOT NULL THEN
    normalized_slug := lower(regexp_replace(requested_tenant_name, '[^a-zA-Z0-9]+', '-', 'g'));
    normalized_slug := trim(both '-' FROM normalized_slug);
    IF normalized_slug = '' THEN
      normalized_slug := 'tenant';
    END IF;

    generated_slug := normalized_slug || '-' || substring(replace(NEW.id::text, '-', ''), 1, 8);

    INSERT INTO public.tenants (slug, name, is_active, metadata)
    VALUES (
      generated_slug,
      requested_tenant_name,
      true,
      jsonb_strip_nulls(
        jsonb_build_object(
          'created_from_signup', true,
          'signup_user_id', NEW.id,
          'plan', requested_plan
        )
      )
    )
    ON CONFLICT (slug) DO UPDATE
    SET
      name = EXCLUDED.name,
      metadata = COALESCE(public.tenants.metadata, '{}'::jsonb) || EXCLUDED.metadata
    RETURNING id INTO resolved_tenant_id;
  END IF;

  -- Upsert app user profile and persist onboarding metadata.
  INSERT INTO public.app_users (user_id, email, full_name, tenant_id, status, metadata)
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    NULLIF(NEW.raw_user_meta_data ->> 'full_name', ''),
    resolved_tenant_id,
    'active',
    jsonb_strip_nulls(
      jsonb_build_object(
        'onboarding_plan', requested_plan,
        'onboarding_default_model_id', requested_model_id,
        'onboarding_device_name', requested_device_name,
        'onboarding_tenant_name', requested_tenant_name
      )
    )
  )
  ON CONFLICT (user_id) DO UPDATE
  SET
    email = EXCLUDED.email,
    full_name = COALESCE(EXCLUDED.full_name, public.app_users.full_name),
    tenant_id = COALESCE(EXCLUDED.tenant_id, public.app_users.tenant_id),
    metadata = COALESCE(public.app_users.metadata, '{}'::jsonb) || EXCLUDED.metadata;

  -- Auto-activate selected model when provided.
  IF requested_model_id IS NOT NULL THEN
    SELECT mc.model_name, mc.domain::public.model_domain
      INTO resolved_model_name, resolved_domain
    FROM public.model_catalog mc
    WHERE mc.model_id = requested_model_id
      AND mc.is_active = true
    LIMIT 1;

    -- Fallbacks for onboarding model ids when catalog row is absent.
    IF resolved_model_name IS NULL THEN
      resolved_model_name := CASE requested_model_id
        WHEN 'quote-generation' THEN 'Quote Generation Agent'
        WHEN 'policy-comparison' THEN 'Policy Comparison Engine'
        WHEN 'document-retrieval' THEN 'Document Retrieval'
        WHEN 'claims-fnol' THEN 'Claims and FNOL Intelligence'
        WHEN 'coverage-validation' THEN 'Coverage Validation and Eligibility'
        ELSE initcap(replace(requested_model_id, '-', ' '))
      END;
    END IF;

    IF resolved_domain IS NULL THEN
      resolved_domain := 'insurance'::public.model_domain;
    END IF;

    INSERT INTO public.activated_models (user_id, model_id, model_name, domain)
    VALUES (NEW.id, requested_model_id, resolved_model_name, resolved_domain)
    ON CONFLICT (user_id, model_id) DO NOTHING;
  END IF;

  -- Create first device record with generated device token.
  IF requested_device_name IS NOT NULL THEN
    INSERT INTO public.devices (device_name, device_token, registered_by, status, metadata)
    VALUES (
      requested_device_name,
      public.generate_device_token(),
      NEW.id,
      'never_checked_in',
      jsonb_build_object('created_from_signup', true, 'signup_user_id', NEW.id)
    );
  END IF;

  RETURN NEW;
END;
$$;

-- ============================================================================
-- END MIGRATION: 20260312233000_signup_onboarding_persistence.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260313001000_device_pairing_sessions.sql
-- ============================================================================
-- WhatsApp-style short-lived pairing sessions for device linking.
CREATE TABLE IF NOT EXISTS public.device_pairings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  pairing_code_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'expired', 'cancelled')),
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ,
  linked_device_id UUID REFERENCES public.devices(id) ON DELETE SET NULL,
  primary_device_label TEXT,
  requested_device_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
  confirmed_device_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_device_pairings_user_status
  ON public.device_pairings(user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_device_pairings_expires_at
  ON public.device_pairings(expires_at);

ALTER TABLE public.device_pairings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own device pairings" ON public.device_pairings;
CREATE POLICY "Users can view own device pairings"
  ON public.device_pairings FOR SELECT
  USING (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Users can insert own device pairings" ON public.device_pairings;
CREATE POLICY "Users can insert own device pairings"
  ON public.device_pairings FOR INSERT
  WITH CHECK (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Users can update own pending pairings" ON public.device_pairings;
CREATE POLICY "Users can update own pending pairings"
  ON public.device_pairings FOR UPDATE
  USING (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'))
  WITH CHECK (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Admins can delete device pairings" ON public.device_pairings;
CREATE POLICY "Admins can delete device pairings"
  ON public.device_pairings FOR DELETE
  USING (public.has_role(auth.uid(), 'admin'));

DROP TRIGGER IF EXISTS update_device_pairings_updated_at ON public.device_pairings;
CREATE TRIGGER update_device_pairings_updated_at
  BEFORE UPDATE ON public.device_pairings
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- END MIGRATION: 20260313001000_device_pairing_sessions.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260313002000_signup_device_profile_persistence.sql
-- ============================================================================
-- Persist complete signup device profile metadata in app_users and devices.
CREATE OR REPLACE FUNCTION public.handle_new_app_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  default_tenant_id UUID;
  resolved_tenant_id UUID;
  requested_tenant_name TEXT;
  requested_plan TEXT;
  requested_role TEXT;
  requested_signup_version TEXT;
  requested_model_id TEXT;
  requested_device_name TEXT;
  requested_device_profile JSONB;
  normalized_slug TEXT;
  generated_slug TEXT;
  resolved_model_name TEXT;
  resolved_domain public.model_domain;
BEGIN
  requested_tenant_name := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'tenant_name', '')), '');
  requested_plan := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'plan', '')), '');
  requested_role := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'requested_role', '')), '');
  requested_signup_version := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'signup_wizard_version', '')), '');
  requested_model_id := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'default_model_id', '')), '');
  requested_device_name := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'device_name', '')), '');
  requested_device_profile := COALESCE(NEW.raw_user_meta_data -> 'device_profile', '{}'::jsonb);
  IF requested_device_name IS NULL THEN
    requested_device_name := NULLIF(trim(COALESCE(requested_device_profile ->> 'device_name', '')), '');
  END IF;

  SELECT id INTO default_tenant_id
  FROM public.tenants
  WHERE slug = 'default-tenant'
  LIMIT 1;

  resolved_tenant_id := default_tenant_id;

  IF requested_tenant_name IS NOT NULL THEN
    normalized_slug := lower(regexp_replace(requested_tenant_name, '[^a-zA-Z0-9]+', '-', 'g'));
    normalized_slug := trim(both '-' FROM normalized_slug);
    IF normalized_slug = '' THEN
      normalized_slug := 'tenant';
    END IF;

    generated_slug := normalized_slug || '-' || substring(replace(NEW.id::text, '-', ''), 1, 8);

    INSERT INTO public.tenants (slug, name, is_active, metadata)
    VALUES (
      generated_slug,
      requested_tenant_name,
      true,
      jsonb_strip_nulls(
        jsonb_build_object(
          'created_from_signup', true,
          'signup_user_id', NEW.id,
          'plan', requested_plan
        )
      )
    )
    ON CONFLICT (slug) DO UPDATE
    SET
      name = EXCLUDED.name,
      metadata = COALESCE(public.tenants.metadata, '{}'::jsonb) || EXCLUDED.metadata
    RETURNING id INTO resolved_tenant_id;
  END IF;

  INSERT INTO public.app_users (user_id, email, full_name, tenant_id, status, metadata)
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    NULLIF(NEW.raw_user_meta_data ->> 'full_name', ''),
    resolved_tenant_id,
    'active',
    jsonb_strip_nulls(
      jsonb_build_object(
        'onboarding_plan', requested_plan,
        'onboarding_requested_role', requested_role,
        'onboarding_signup_wizard_version', requested_signup_version,
        'onboarding_default_model_id', requested_model_id,
        'onboarding_device_name', requested_device_name,
        'onboarding_tenant_name', requested_tenant_name,
        'onboarding_device_profile', requested_device_profile
      )
    )
  )
  ON CONFLICT (user_id) DO UPDATE
  SET
    email = EXCLUDED.email,
    full_name = COALESCE(EXCLUDED.full_name, public.app_users.full_name),
    tenant_id = COALESCE(EXCLUDED.tenant_id, public.app_users.tenant_id),
    metadata = COALESCE(public.app_users.metadata, '{}'::jsonb) || EXCLUDED.metadata;

  IF requested_model_id IS NOT NULL THEN
    SELECT mc.model_name, mc.domain::public.model_domain
      INTO resolved_model_name, resolved_domain
    FROM public.model_catalog mc
    WHERE mc.model_id = requested_model_id
      AND mc.is_active = true
    LIMIT 1;

    IF resolved_model_name IS NULL THEN
      resolved_model_name := CASE requested_model_id
        WHEN 'quote-generation' THEN 'Quote Generation Agent'
        WHEN 'policy-comparison' THEN 'Policy Comparison Engine'
        WHEN 'document-retrieval' THEN 'Document Retrieval'
        WHEN 'claims-fnol' THEN 'Claims and FNOL Intelligence'
        WHEN 'coverage-validation' THEN 'Coverage Validation and Eligibility'
        ELSE initcap(replace(requested_model_id, '-', ' '))
      END;
    END IF;

    IF resolved_domain IS NULL THEN
      resolved_domain := 'insurance'::public.model_domain;
    END IF;

    INSERT INTO public.activated_models (user_id, model_id, model_name, domain)
    VALUES (NEW.id, requested_model_id, resolved_model_name, resolved_domain)
    ON CONFLICT (user_id, model_id) DO NOTHING;
  END IF;

  IF requested_device_name IS NOT NULL THEN
    INSERT INTO public.devices (device_name, device_token, registered_by, status, os_type, app_version, metadata)
    VALUES (
      requested_device_name,
      public.generate_device_token(),
      NEW.id,
      'never_checked_in',
      NULLIF(requested_device_profile ->> 'os_name', ''),
      NULLIF(requested_device_profile ->> 'app_version', ''),
      jsonb_strip_nulls(
        jsonb_build_object(
          'created_from_signup', true,
          'signup_user_id', NEW.id,
          'device_profile', requested_device_profile
        )
      )
    );
  END IF;

  RETURN NEW;
END;
$$;

-- ============================================================================
-- END MIGRATION: 20260313002000_signup_device_profile_persistence.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260313091500_auth_audit_logs.sql
-- ============================================================================
-- Audit log table for auth activity (logins, logouts, approvals, etc.)

create table if not exists public.auth_audit (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null
);

-- Ensure expected columns exist even if table was created earlier
alter table public.auth_audit
  add column if not exists email text;

alter table public.auth_audit
  add column if not exists role text;

alter table public.auth_audit
  add column if not exists event text;

alter table public.auth_audit
  add column if not exists created_at timestamptz not null default now();

-- Normalized ATNA-style fields
-- action_code: C=Create, R=Read, U=Update, D=Delete, E=Execute
alter table public.auth_audit
  add column if not exists action_code text;

-- outcome_code: 0=Success, 4=Minor failure, 8=Serious, 12=Major
alter table public.auth_audit
  add column if not exists outcome_code integer;

alter table public.auth_audit
  add column if not exists resource_type text;

alter table public.auth_audit
  add column if not exists resource_id text;

-- Integrity hash for tamper-evidence (no PII). Hash is computed over:
-- user_id, role, event, action_code, outcome_code, resource_type, resource_id, created_at
alter table public.auth_audit
  add column if not exists integrity_hash text;

alter table public.auth_audit enable row level security;

-- Users can insert their own audit rows
drop policy if exists "Users can insert their own auth audit" on public.auth_audit;
create policy "Users can insert their own auth audit"
on public.auth_audit
for insert
with check (auth.uid() = user_id);

-- Users see only their own activity
drop policy if exists "Users see own auth audit" on public.auth_audit;
create policy "Users see own auth audit"
on public.auth_audit
for select
using (user_id = auth.uid());

-- Admins can see user + admin + viewer + guest activity (but not global_admin)
drop policy if exists "Admins see user+admin auth audit" on public.auth_audit;
create policy "Admins see user+admin auth audit"
on public.auth_audit
for select
using (
  public.has_role(auth.uid(), 'admin'::public.app_role)
  and role in ('admin', 'user', 'viewer', 'guest')
);

-- Global admins can see all audit activity
drop policy if exists "Global admins see all auth audit" on public.auth_audit;
create policy "Global admins see all auth audit"
on public.auth_audit
for select
using (
  public.has_role(auth.uid(), 'global_admin'::public.app_role)
);


-- ============================================================================
-- END MIGRATION: 20260313091500_auth_audit_logs.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260313100000_agent_domain_catalog.sql
-- ============================================================================
-- Domain and Agent catalog for RAG-aware agents

create table if not exists public.domain_catalog (
  id text primary key,
  display_name text not null,
  description text,
  rag_collection text,
  default_model_adapter text,
  data_path text,
  is_active boolean not null default true
);

create table if not exists public.agent_catalog (
  id text primary key,
  display_name text not null,
  domain_id text not null references public.domain_catalog(id) on delete cascade,
  category text,
  description text,
  system_prompt text,
  output_schema jsonb,
  rag_collection_override text,
  model_adapter_override text,
  tools jsonb,
  is_active boolean not null default true
);


-- ============================================================================
-- END MIGRATION: 20260313100000_agent_domain_catalog.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260316000000_auth_audit_user_id_fk.sql
-- ============================================================================
-- Add foreign key constraint from auth_audit.user_id to auth.users(id)
-- This enforces referential integrity: audit rows cannot exist for deleted users.

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'auth_audit_user_id_fkey'
      and conrelid = 'public.auth_audit'::regclass
  ) then
    alter table public.auth_audit
      add constraint auth_audit_user_id_fkey
      foreign key (user_id) references auth.users(id) on delete cascade;
  end if;
end $$;

-- ============================================================================
-- END MIGRATION: 20260316000000_auth_audit_user_id_fk.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260316000001_audit_immutability.sql
-- ============================================================================
-- ============================================================
-- Immutable Audit Log Enforcement
-- EU AI Act (Art. 12/13), SOC2 (CC7.2/CC9.1), NAIC AI Bulletin
-- ============================================================
-- Audit rows must be append-only. No UPDATE or DELETE is ever
-- permitted â€” not by users, not by admins, not by service_role.
-- Triggers fire before the operation regardless of RLS bypass.
-- Only a Postgres superuser running ALTER TABLE ... DISABLE TRIGGER
-- can circumvent this, and that action itself is logged by Postgres.
-- ============================================================

-- Shared trigger function: raises an exception on any modification attempt.
CREATE OR REPLACE FUNCTION public.prevent_audit_modification()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RAISE EXCEPTION
    'Audit log records are immutable (EU AI Act Art.12 / SOC2 CC7.2 / NAIC). '
    'Operation "%" on table "%" is not permitted.',
    TG_OP, TG_TABLE_NAME;
END;
$$;

-- â”€â”€ auth_audit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
DROP TRIGGER IF EXISTS auth_audit_no_update ON public.auth_audit;
CREATE TRIGGER auth_audit_no_update
  BEFORE UPDATE ON public.auth_audit
  FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_modification();

DROP TRIGGER IF EXISTS auth_audit_no_delete ON public.auth_audit;
CREATE TRIGGER auth_audit_no_delete
  BEFORE DELETE ON public.auth_audit
  FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_modification();

-- â”€â”€ audit_logs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
DROP TRIGGER IF EXISTS audit_logs_no_update ON public.audit_logs;
CREATE TRIGGER audit_logs_no_update
  BEFORE UPDATE ON public.audit_logs
  FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_modification();

DROP TRIGGER IF EXISTS audit_logs_no_delete ON public.audit_logs;
CREATE TRIGGER audit_logs_no_delete
  BEFORE DELETE ON public.audit_logs
  FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_modification();

-- â”€â”€ Add integrity_hash to audit_logs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
-- auth_audit already has this column. audit_logs was missing it.
-- Hash is computed by the caller over: user_id, action,
-- resource_type, resource_id, created_at (non-PII fields).
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS integrity_hash TEXT;

-- â”€â”€ Retention comment (operational requirement) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
-- EU AI Act requires logs retained â‰¥ 6 months for deployers.
-- SOC2 / NAIC typically require â‰¥ 12 months.
-- Implement via pg_cron archival to cold storage â€” DO NOT DELETE.
-- Example (run separately after enabling pg_cron extension):
--
--   SELECT cron.schedule(
--     'archive-old-audit-logs',
--     '0 2 * * 0',   -- every Sunday at 02:00 UTC
--     $$
--       INSERT INTO public.audit_logs_archive SELECT * FROM public.audit_logs
--         WHERE created_at < now() - interval '13 months';
--       -- Note: DELETE from live table requires disabling trigger temporarily
--       -- under a controlled, logged superuser session only.
--     $$
--   );

-- ============================================================================
-- END MIGRATION: 20260316000001_audit_immutability.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260316000002_audit_logs_change_tracking.sql
-- ============================================================================
-- ============================================================
-- Change Tracking: previous_value / new_value columns
-- audit_logs â€” backend API audit trail
-- ============================================================
-- Stores the before/after state of a changed resource so every
-- audit row is a self-contained change record.
-- Both columns are JSONB so structured diffs can be queried.
-- PII/PHA (emails, names, passwords) must NEVER appear in these
-- columns â€” callers are responsible for passing only safe fields
-- (role names, status strings, model IDs, UUIDs).
-- Both columns are included in the SHA-256 integrity_hash so any
-- post-write tampering is detectable.
-- ============================================================

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS previous_value JSONB;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS new_value JSONB;

-- Index: fast lookup of all changes to a specific resource
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_id
  ON public.audit_logs (resource_id)
  WHERE resource_id IS NOT NULL;

-- ============================================================================
-- END MIGRATION: 20260316000002_audit_logs_change_tracking.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260316000003_device_hardware_fingerprint.sql
-- ============================================================================
-- Add hardware_fingerprint_hash column to devices table for idempotent device registration.
-- The column stores a SHA-256 hash of the raw hardware fingerprint (never the raw value).
-- UNIQUE constraint ensures one device record per physical device.
-- Nullable to preserve backward compatibility with existing devices created via pairing.

ALTER TABLE devices
  ADD COLUMN IF NOT EXISTS hardware_fingerprint_hash TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS devices_hardware_fingerprint_hash_key
  ON devices (hardware_fingerprint_hash)
  WHERE hardware_fingerprint_hash IS NOT NULL;

COMMENT ON COLUMN devices.hardware_fingerprint_hash IS
  'SHA-256 hex digest of the device hardware fingerprint. NULL for devices created via pairing flow.';

-- ============================================================================
-- END MIGRATION: 20260316000003_device_hardware_fingerprint.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260316000004_devices_realtime.sql
-- ============================================================================
-- Enable Supabase Realtime for the devices table so the UI receives
-- live status updates (online â†’ offline) without polling.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_publication_rel pr
    JOIN pg_class c ON c.oid = pr.prrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_publication p ON p.oid = pr.prpubid
    WHERE p.pubname = 'supabase_realtime'
      AND n.nspname = 'public'
      AND c.relname = 'devices'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.devices;
  END IF;
END $$;

-- ============================================================================
-- END MIGRATION: 20260316000004_devices_realtime.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260316000005_rename_auth_audit_admin_policy.sql
-- ============================================================================
-- ============================================================
-- Correction 5: Rename misleading RLS policy on auth_audit
-- Old name: "Admins see user+admin auth audit"
--   â†’ implied only admin+user rows visible, omitted viewer+guest
-- New name: "Admins see all except global_admin auth audit"
--   â†’ accurately describes the condition: role IN (admin, user, viewer, guest)
-- The condition itself is unchanged â€” only the policy name is corrected.
-- ============================================================

-- Drop old misleadingly-named policy
DROP POLICY IF EXISTS "Admins see user+admin auth audit" ON public.auth_audit;

-- Recreate with accurate name
DROP POLICY IF EXISTS "Admins see all except global_admin auth audit" ON public.auth_audit;
CREATE POLICY "Admins see all except global_admin auth audit"
ON public.auth_audit
FOR SELECT
USING (
  public.has_role(auth.uid(), 'admin'::public.app_role)
  AND role IN ('admin', 'user', 'viewer', 'guest')
);

-- ============================================================================
-- END MIGRATION: 20260316000005_rename_auth_audit_admin_policy.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260317000000_devices_replica_identity_full.sql
-- ============================================================================
-- Enable REPLICA IDENTITY FULL on the devices table so that Supabase Realtime
-- includes both old and new row values in UPDATE event payloads.
-- This allows the frontend to compare old.status vs new.status and skip
-- unnecessary re-fetches on heartbeat-only updates (last_seen_at changes).
ALTER TABLE devices REPLICA IDENTITY FULL;

-- ============================================================================
-- END MIGRATION: 20260317000000_devices_replica_identity_full.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260317000001_devices_production_hardening.sql
-- ============================================================================
-- Production hardening for the devices table.
--
-- 1. Composite index used by the offline detector sweep:
--      WHERE status = 'online' AND last_seen_at < <threshold>
--    The two existing single-column indexes (idx_devices_status,
--    idx_devices_last_seen) force PostgreSQL into an index intersection or a
--    sequential scan on large tables. A composite index eliminates that.
--
-- 2. jwt_issued_after â€” soft JWT revocation without a blocklist table.
--    The backend sets this to NOW() whenever a new device token is issued.
--    The heartbeat endpoint rejects any JWT whose `iat` predates this value,
--    which means re-registering a device automatically invalidates all
--    previously issued tokens for that device.
--    Admins can also set it to NOW() to immediately revoke all active tokens.

CREATE INDEX IF NOT EXISTS idx_devices_status_last_seen
    ON public.devices (status, last_seen_at DESC);

ALTER TABLE public.devices
    ADD COLUMN IF NOT EXISTS jwt_issued_after TIMESTAMPTZ
    NOT NULL DEFAULT '1970-01-01T00:00:00Z';

-- ============================================================================
-- END MIGRATION: 20260317000001_devices_production_hardening.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260317000002_audit_ledger_shap.sql
-- ============================================================================
-- ============================================================
-- Audit Ledger: Cryptographic Chain + SHAP AI Reasoning
-- ============================================================
-- Upgrades audit_logs to a full cryptographic ledger by adding:
--
--   sequence_num  â€” IDENTITY column: strict monotonic insert order
--   chain_hash    â€” SHA-256(prev_chain_hash âˆ¥ integrity_hash)
--                   Each row binds to its predecessor, so inserting,
--                   removing, or reordering any row invalidates every
--                   chain_hash that follows it.
--
-- Adds AI explainability columns for SHAP-based reasoning:
--
--   shap_values   â€” JSONB: {feature_name: shap_float, ...}
--   model_id      â€” identifier of the model that produced the decision
--   prediction    â€” model output / decision outcome (JSONB)
--   reasoning     â€” auto-generated human-readable SHAP explanation
--
-- All five new fields are included in the per-row integrity_hash
-- (computed by the application layer in supabase.py) so tampering
-- with any field breaks both the row hash and the ledger chain.
--
-- Compliance: EU AI Act Art.12/13, SOC2 CC7.2, NAIC AI Bulletin
-- ============================================================

-- pgcrypto is required for the SHA-256 chain computation in the trigger.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- â”€â”€ New columns â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

-- sequence_num: monotonic insert order â€” never supplied by the caller.
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS sequence_num BIGINT GENERATED ALWAYS AS IDENTITY;

-- chain_hash: set exclusively by the trigger below, never by the caller.
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS chain_hash TEXT;

-- SHAP / AI explainability fields (nullable â€” only present on AI decisions).
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS shap_values JSONB;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS model_id TEXT;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS prediction JSONB;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS reasoning TEXT;

-- â”€â”€ Indexes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

-- Fast "latest block" lookup used by the chain trigger.
CREATE INDEX IF NOT EXISTS idx_audit_logs_sequence_num
  ON public.audit_logs (sequence_num DESC);

-- Filter AI-decision rows quickly (WHERE model_id IS NOT NULL).
CREATE INDEX IF NOT EXISTS idx_audit_logs_model_id
  ON public.audit_logs (model_id)
  WHERE model_id IS NOT NULL;

-- â”€â”€ Chain Hash Trigger â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
-- Fires BEFORE INSERT; overwrites chain_hash with the computed value.
-- Uses pg_advisory_xact_lock to serialise concurrent inserts, ensuring
-- the chain is always linear (no forks or ties between parallel writers).

CREATE OR REPLACE FUNCTION public.compute_audit_chain_hash()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  prev_chain_hash TEXT;
BEGIN
  -- Acquire a session-scoped advisory lock so concurrent inserts queue
  -- behind each other and always read the true latest chain_hash.
  PERFORM pg_advisory_xact_lock(hashtext('audit_ledger_chain'));

  SELECT chain_hash
    INTO prev_chain_hash
    FROM public.audit_logs
   ORDER BY sequence_num DESC
   LIMIT 1;

  -- Genesis block: no previous row exists yet.
  IF prev_chain_hash IS NULL THEN
    prev_chain_hash := 'GENESIS';
  END IF;

  -- chain_hash_N = SHA-256( chain_hash_{N-1} || integrity_hash_N )
  NEW.chain_hash := encode(
    digest(prev_chain_hash || COALESCE(NEW.integrity_hash, ''), 'sha256'),
    'hex'
  );

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS audit_logs_chain_hash ON public.audit_logs;
CREATE TRIGGER audit_logs_chain_hash
  BEFORE INSERT ON public.audit_logs
  FOR EACH ROW
  EXECUTE FUNCTION public.compute_audit_chain_hash();

-- â”€â”€ Ledger Verification Function â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
-- Walks the entire ledger in sequence order and re-derives every
-- chain_hash from scratch.  Rows where stored_chain â‰  computed_chain
-- indicate tampering (insertion, deletion, or modification).
--
-- Usage:
--   SELECT * FROM public.verify_audit_ledger() WHERE NOT is_valid;

CREATE OR REPLACE FUNCTION public.verify_audit_ledger()
RETURNS TABLE (
  sequence_num   BIGINT,
  id             UUID,
  stored_chain   TEXT,
  computed_chain TEXT,
  is_valid       BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  rec            RECORD;
  prev_chain     TEXT := 'GENESIS';
  expected_chain TEXT;
BEGIN
  FOR rec IN
    SELECT al.sequence_num, al.id, al.integrity_hash, al.chain_hash
      FROM public.audit_logs al
     ORDER BY al.sequence_num ASC
  LOOP
    expected_chain := encode(
      digest(prev_chain || COALESCE(rec.integrity_hash, ''), 'sha256'),
      'hex'
    );

    RETURN QUERY SELECT
      rec.sequence_num,
      rec.id,
      rec.chain_hash   AS stored_chain,
      expected_chain   AS computed_chain,
      (rec.chain_hash = expected_chain) AS is_valid;

    prev_chain := rec.chain_hash;
  END LOOP;
END;
$$;

-- ============================================================================
-- END MIGRATION: 20260317000002_audit_ledger_shap.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260317000003_verify_audit_ledger_fix.sql
-- ============================================================================
-- ============================================================
-- Fix: verify_audit_ledger() â€” pre-migration NULL chain rows
-- ============================================================
-- Rows that existed before migration 20260317000002 have
-- chain_hash = NULL because the trigger had not yet been
-- created.  The original function propagated NULL into
-- prev_chain, causing NULL || integrity_hash = NULL in
-- PostgreSQL string concatenation, which silently broke
-- chain verification for every row that followed.
--
-- Fix: when chain_hash IS NULL, emit the row as a
-- "pre-migration" sentinel (is_valid = NULL) and do NOT
-- advance prev_chain, keeping it at 'GENESIS' until the
-- first post-migration row establishes the chain.
--
-- This is safe because:
--   â€¢ The trigger uses the same GENESIS seed for the first
--     post-migration insert (any existing row it reads has
--     chain_hash = NULL, so the IF IS NULL guard fires).
--   â€¢ Subsequent post-migration rows chain correctly from
--     the first post-migration chain_hash onward.
-- ============================================================

CREATE OR REPLACE FUNCTION public.verify_audit_ledger()
RETURNS TABLE (
  sequence_num   BIGINT,
  id             UUID,
  stored_chain   TEXT,
  computed_chain TEXT,
  is_valid       BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  rec            RECORD;
  prev_chain     TEXT := 'GENESIS';
  expected_chain TEXT;
BEGIN
  FOR rec IN
    SELECT al.sequence_num, al.id, al.integrity_hash, al.chain_hash
      FROM public.audit_logs al
     ORDER BY al.sequence_num ASC
  LOOP
    -- Pre-migration rows have chain_hash = NULL.
    -- Report them as sentinel entries and keep prev_chain unchanged
    -- so the first post-migration row still verifies against GENESIS.
    IF rec.chain_hash IS NULL THEN
      RETURN QUERY SELECT
        rec.sequence_num,
        rec.id,
        NULL::TEXT  AS stored_chain,
        NULL::TEXT  AS computed_chain,
        NULL::BOOLEAN AS is_valid;
      CONTINUE;  -- do NOT update prev_chain
    END IF;

    expected_chain := encode(
      digest(prev_chain || COALESCE(rec.integrity_hash, ''), 'sha256'),
      'hex'
    );

    RETURN QUERY SELECT
      rec.sequence_num,
      rec.id,
      rec.chain_hash   AS stored_chain,
      expected_chain   AS computed_chain,
      (rec.chain_hash = expected_chain) AS is_valid;

    prev_chain := rec.chain_hash;
  END LOOP;
END;
$$;

-- ============================================================================
-- END MIGRATION: 20260317000003_verify_audit_ledger_fix.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260317100000_tenant_scope_rls_hardening.sql
-- ============================================================================
-- Tenant-scope RLS hardening (shared-schema model).
-- Goal: keep existing architecture while preventing cross-tenant data access
-- for admin users. global_admin retains cross-tenant visibility.

-- app_users: tenant-bounded admin access
DROP POLICY IF EXISTS "Admins can view all app users" ON public.app_users;
DROP POLICY IF EXISTS "Admins can manage app users" ON public.app_users;

DROP POLICY IF EXISTS "Admins can view app users in own tenant" ON public.app_users;
CREATE POLICY "Admins can view app users in own tenant"
  ON public.app_users
  FOR SELECT
  USING (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = public.app_users.tenant_id
    )
  );

DROP POLICY IF EXISTS "Admins can manage app users in own tenant" ON public.app_users;
CREATE POLICY "Admins can manage app users in own tenant"
  ON public.app_users
  FOR ALL
  USING (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = public.app_users.tenant_id
    )
  )
  WITH CHECK (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = public.app_users.tenant_id
    )
  );

DROP POLICY IF EXISTS "Global admins can manage all app users" ON public.app_users;
CREATE POLICY "Global admins can manage all app users"
  ON public.app_users
  FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- tenants: global_admin can manage all; admin can only manage own tenant row
DROP POLICY IF EXISTS "Admins can manage all tenants" ON public.tenants;

DROP POLICY IF EXISTS "Admins can manage own tenant" ON public.tenants;
CREATE POLICY "Admins can manage own tenant"
  ON public.tenants
  FOR ALL
  USING (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      WHERE me.user_id = auth.uid()
        AND me.tenant_id = public.tenants.id
    )
  )
  WITH CHECK (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      WHERE me.user_id = auth.uid()
        AND me.tenant_id = public.tenants.id
    )
  );

DROP POLICY IF EXISTS "Global admins can manage all tenants" ON public.tenants;
CREATE POLICY "Global admins can manage all tenants"
  ON public.tenants
  FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- user_roles: tenant-bounded admin role management
DROP POLICY IF EXISTS "Admins can view all user roles" ON public.user_roles;
DROP POLICY IF EXISTS "Admins can insert user roles" ON public.user_roles;
DROP POLICY IF EXISTS "Admins can update user roles" ON public.user_roles;
DROP POLICY IF EXISTS "Admins can delete user roles" ON public.user_roles;

DROP POLICY IF EXISTS "Admins can view user roles in own tenant" ON public.user_roles;
CREATE POLICY "Admins can view user roles in own tenant"
  ON public.user_roles
  FOR SELECT
  USING (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      JOIN public.app_users target ON target.user_id = public.user_roles.user_id
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = target.tenant_id
    )
  );

DROP POLICY IF EXISTS "Admins can insert user roles in own tenant" ON public.user_roles;
CREATE POLICY "Admins can insert user roles in own tenant"
  ON public.user_roles
  FOR INSERT
  WITH CHECK (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      JOIN public.app_users target ON target.user_id = public.user_roles.user_id
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = target.tenant_id
    )
  );

DROP POLICY IF EXISTS "Admins can update user roles in own tenant" ON public.user_roles;
CREATE POLICY "Admins can update user roles in own tenant"
  ON public.user_roles
  FOR UPDATE
  USING (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      JOIN public.app_users target ON target.user_id = public.user_roles.user_id
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = target.tenant_id
    )
  )
  WITH CHECK (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      JOIN public.app_users target ON target.user_id = public.user_roles.user_id
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = target.tenant_id
    )
  );

DROP POLICY IF EXISTS "Admins can delete user roles in own tenant" ON public.user_roles;
CREATE POLICY "Admins can delete user roles in own tenant"
  ON public.user_roles
  FOR DELETE
  USING (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      JOIN public.app_users target ON target.user_id = public.user_roles.user_id
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = target.tenant_id
    )
  );

DROP POLICY IF EXISTS "Global admins can manage all user roles" ON public.user_roles;
CREATE POLICY "Global admins can manage all user roles"
  ON public.user_roles
  FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- devices: tenant-bounded admin visibility/management
DROP POLICY IF EXISTS "Admins can view all devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can insert devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can update devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can delete devices" ON public.devices;

DROP POLICY IF EXISTS "Admins can view devices in own tenant" ON public.devices;
CREATE POLICY "Admins can view devices in own tenant"
  ON public.devices
  FOR SELECT
  USING (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      JOIN public.app_users owner ON owner.user_id = public.devices.registered_by
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = owner.tenant_id
    )
  );

DROP POLICY IF EXISTS "Admins can insert devices in own tenant" ON public.devices;
CREATE POLICY "Admins can insert devices in own tenant"
  ON public.devices
  FOR INSERT
  WITH CHECK (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      JOIN public.app_users owner ON owner.user_id = public.devices.registered_by
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = owner.tenant_id
    )
  );

DROP POLICY IF EXISTS "Admins can update devices in own tenant" ON public.devices;
CREATE POLICY "Admins can update devices in own tenant"
  ON public.devices
  FOR UPDATE
  USING (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      JOIN public.app_users owner ON owner.user_id = public.devices.registered_by
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = owner.tenant_id
    )
  )
  WITH CHECK (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      JOIN public.app_users owner ON owner.user_id = public.devices.registered_by
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = owner.tenant_id
    )
  );

DROP POLICY IF EXISTS "Admins can delete devices in own tenant" ON public.devices;
CREATE POLICY "Admins can delete devices in own tenant"
  ON public.devices
  FOR DELETE
  USING (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    AND EXISTS (
      SELECT 1
      FROM public.app_users me
      JOIN public.app_users owner ON owner.user_id = public.devices.registered_by
      WHERE me.user_id = auth.uid()
        AND me.tenant_id IS NOT NULL
        AND me.tenant_id = owner.tenant_id
    )
  );

DROP POLICY IF EXISTS "Global admins can manage all devices" ON public.devices;
CREATE POLICY "Global admins can manage all devices"
  ON public.devices
  FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- ============================================================================
-- END MIGRATION: 20260317100000_tenant_scope_rls_hardening.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260317110000_realtime_notifications.sql
-- ============================================================================
-- Enable Supabase Realtime for notification-oriented tables used by
-- the global login-time subscription manager.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'pod_activation_requests'
  ) AND NOT EXISTS (
    SELECT 1
    FROM pg_publication_rel pr
    JOIN pg_class c ON c.oid = pr.prrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_publication p ON p.oid = pr.prpubid
    WHERE p.pubname = 'supabase_realtime'
      AND n.nspname = 'public'
      AND c.relname = 'pod_activation_requests'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.pod_activation_requests;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'device_sync_logs'
  ) AND NOT EXISTS (
    SELECT 1
    FROM pg_publication_rel pr
    JOIN pg_class c ON c.oid = pr.prrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_publication p ON p.oid = pr.prpubid
    WHERE p.pubname = 'supabase_realtime'
      AND n.nspname = 'public'
      AND c.relname = 'device_sync_logs'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.device_sync_logs;
  END IF;
END $$;

-- ============================================================================
-- END MIGRATION: 20260317110000_realtime_notifications.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260317113000_settings_personal_api_keys.sql
-- ============================================================================
-- Personal API keys for Settings page (profile/preferences/API keys).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.personal_api_keys (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name text NOT NULL CHECK (length(name) > 0 AND length(name) <= 80),
  key_prefix text NOT NULL CHECK (length(key_prefix) >= 8),
  key_hash_sha256 text NOT NULL UNIQUE CHECK (length(key_hash_sha256) = 64),
  key_prefix_sha256 text NOT NULL CHECK (length(key_prefix_sha256) >= 8),
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  last_used_at timestamptz NULL,
  revoked_at timestamptz NULL
);

CREATE INDEX IF NOT EXISTS idx_personal_api_keys_user_id
  ON public.personal_api_keys (user_id);

CREATE INDEX IF NOT EXISTS idx_personal_api_keys_created_at
  ON public.personal_api_keys (created_at DESC);

ALTER TABLE public.personal_api_keys ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own personal api keys" ON public.personal_api_keys;
CREATE POLICY "Users can view own personal api keys"
  ON public.personal_api_keys
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create own personal api keys" ON public.personal_api_keys;
CREATE POLICY "Users can create own personal api keys"
  ON public.personal_api_keys
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own personal api keys" ON public.personal_api_keys;
CREATE POLICY "Users can update own personal api keys"
  ON public.personal_api_keys
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- ============================================================================
-- END MIGRATION: 20260317113000_settings_personal_api_keys.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260317120000_fix_permissive_rls_and_missing_delete.sql
-- ============================================================================
-- Fix 1: personal_api_keys missing DELETE policy
DROP POLICY IF EXISTS "Users can delete own personal api keys" ON public.personal_api_keys;
CREATE POLICY "Users can delete own personal api keys"
  ON public.personal_api_keys
  FOR DELETE
  USING (auth.uid() = user_id);

-- Fix 2: training_jobs had USING (true) FOR ALL â€” any user could read/modify any job
DROP POLICY IF EXISTS "Device functions can manage training jobs" ON public.training_jobs;

-- Only admins can manage training jobs directly (device firmware uses service_role)
DROP POLICY IF EXISTS "Admins can manage training jobs" ON public.training_jobs;
CREATE POLICY "Admins can manage training jobs"
  ON public.training_jobs FOR ALL
  USING (public.has_role(auth.uid(), 'admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

-- Fix 3: federated_updates INSERT had WITH CHECK (true) â€” any user could insert for any device
DROP POLICY IF EXISTS "Device functions can insert updates" ON public.federated_updates;

-- Only admins can insert federated updates directly (devices use service_role)
DROP POLICY IF EXISTS "Admins can insert federated updates" ON public.federated_updates;
CREATE POLICY "Admins can insert federated updates"
  ON public.federated_updates FOR INSERT
  WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

-- Fix 4: user_roles tenant-JOIN policy caused 500 errors on every role lookup
-- The JOIN to app_users inside an RLS policy creates a cascading evaluation crash
DROP POLICY IF EXISTS "Admins can view user roles in own tenant" ON public.user_roles;
DROP POLICY IF EXISTS "Admins can view all user roles" ON public.user_roles;
CREATE POLICY "Admins can view all user roles"
  ON public.user_roles
  FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'::public.app_role));

-- ============================================================================
-- END MIGRATION: 20260317120000_fix_permissive_rls_and_missing_delete.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260317130000_fix_app_users_infinite_recursion.sql
-- ============================================================================
-- Fix infinite recursion (42P17) in app_users, devices, tenants, and user_roles RLS policies.
-- Root cause: 20260317100000_tenant_scope_rls_hardening.sql introduced policies on app_users
-- that do EXISTS (SELECT 1 FROM public.app_users me ...) â€” a self-referential subquery that
-- triggers the same RLS policy, causing infinite recursion.
--
-- Fix: replace all tenant-JOIN policies with simple has_role() checks.
-- Devices and tenants also referenced app_users inside their policies, causing the same 500.

-- â”€â”€ app_users â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

DROP POLICY IF EXISTS "Admins can view app users in own tenant"    ON public.app_users;
DROP POLICY IF EXISTS "Admins can manage app users in own tenant"  ON public.app_users;
DROP POLICY IF EXISTS "Global admins can manage all app users"     ON public.app_users;

-- Self-view: every authenticated user can see their own row
DROP POLICY IF EXISTS "Users can view own app user record"         ON public.app_users;
CREATE POLICY "Users can view own app user record"
  ON public.app_users FOR SELECT
  USING (auth.uid() = user_id);

-- Admins can view all app users (no self-referential JOIN)
DROP POLICY IF EXISTS "Admins can view all app users"              ON public.app_users;
CREATE POLICY "Admins can view all app users"
  ON public.app_users FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'::public.app_role));

-- Global admins can do everything
DROP POLICY IF EXISTS "Global admins can manage all app users"     ON public.app_users;
CREATE POLICY "Global admins can manage all app users"
  ON public.app_users FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- â”€â”€ tenants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

DROP POLICY IF EXISTS "Admins can manage own tenant"         ON public.tenants;
DROP POLICY IF EXISTS "Global admins can manage all tenants" ON public.tenants;
DROP POLICY IF EXISTS "Admins can view all tenants"          ON public.tenants;

CREATE POLICY "Admins can view all tenants"
  ON public.tenants FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'::public.app_role));

DROP POLICY IF EXISTS "Global admins can manage all tenants" ON public.tenants;
CREATE POLICY "Global admins can manage all tenants"
  ON public.tenants FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- â”€â”€ user_roles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
-- (tenant-JOIN policies were already dropped in 20260317120000, but drop again for safety)

DROP POLICY IF EXISTS "Admins can view user roles in own tenant"    ON public.user_roles;
DROP POLICY IF EXISTS "Admins can insert user roles in own tenant"  ON public.user_roles;
DROP POLICY IF EXISTS "Admins can update user roles in own tenant"  ON public.user_roles;
DROP POLICY IF EXISTS "Admins can delete user roles in own tenant"  ON public.user_roles;
DROP POLICY IF EXISTS "Global admins can manage all user roles"     ON public.user_roles;

-- Already recreated correctly in 20260317120000, just add global_admin + write policies
DROP POLICY IF EXISTS "Admins can view all user roles" ON public.user_roles;
CREATE POLICY "Admins can view all user roles"
  ON public.user_roles FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'::public.app_role));

DROP POLICY IF EXISTS "Admins can manage all user roles" ON public.user_roles;
CREATE POLICY "Admins can manage all user roles"
  ON public.user_roles FOR ALL
  USING (public.has_role(auth.uid(), 'admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

DROP POLICY IF EXISTS "Global admins can manage all user roles" ON public.user_roles;
CREATE POLICY "Global admins can manage all user roles"
  ON public.user_roles FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- â”€â”€ devices â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

DROP POLICY IF EXISTS "Admins can view devices in own tenant"    ON public.devices;
DROP POLICY IF EXISTS "Admins can insert devices in own tenant"  ON public.devices;
DROP POLICY IF EXISTS "Admins can update devices in own tenant"  ON public.devices;
DROP POLICY IF EXISTS "Admins can delete devices in own tenant"  ON public.devices;
DROP POLICY IF EXISTS "Global admins can manage all devices"     ON public.devices;
DROP POLICY IF EXISTS "Admins can view all devices"              ON public.devices;
DROP POLICY IF EXISTS "Admins can manage all devices"            ON public.devices;

CREATE POLICY "Admins can view all devices"
  ON public.devices FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'::public.app_role));

CREATE POLICY "Admins can manage all devices"
  ON public.devices FOR ALL
  USING (public.has_role(auth.uid(), 'admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

DROP POLICY IF EXISTS "Global admins can manage all devices"     ON public.devices;
CREATE POLICY "Global admins can manage all devices"
  ON public.devices FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- ============================================================================
-- END MIGRATION: 20260317130000_fix_app_users_infinite_recursion.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260318000000_user_creation_requests.sql
-- ============================================================================
-- â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
-- User Creation Requests
-- Approval workflow: adminâ†’admin needs global_admin approval;
--                   userâ†’user needs admin or global_admin approval.
-- â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

CREATE TABLE IF NOT EXISTS public.user_creation_requests (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  requested_by     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  requester_role   TEXT        NOT NULL CHECK (requester_role IN ('admin', 'user')),
  email            TEXT        NOT NULL,
  full_name        TEXT,
  requested_role   TEXT        NOT NULL CHECK (requested_role IN ('global_admin','admin','user','viewer','guest')),
  status           TEXT        NOT NULL DEFAULT 'pending'
                               CHECK (status IN ('pending', 'approved', 'rejected')),
  reviewed_by      UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
  rejection_reason TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at      TIMESTAMPTZ
);

-- Index for fast pending-request queries
CREATE INDEX IF NOT EXISTS ucr_status_idx ON public.user_creation_requests (status);
CREATE INDEX IF NOT EXISTS ucr_requested_by_idx ON public.user_creation_requests (requested_by);

-- â”€â”€ Row-Level Security â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ALTER TABLE public.user_creation_requests ENABLE ROW LEVEL SECURITY;

-- Requesters can see their own requests
DROP POLICY IF EXISTS "ucr_requester_select" ON public.user_creation_requests;
CREATE POLICY "ucr_requester_select"
  ON public.user_creation_requests FOR SELECT
  USING (requested_by = auth.uid());

-- Admins (and global_admin via has_role hierarchy) can see all requests
DROP POLICY IF EXISTS "ucr_admin_select" ON public.user_creation_requests;
CREATE POLICY "ucr_admin_select"
  ON public.user_creation_requests FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'));

-- Any authenticated user whose role is 'admin' or 'user' can submit a request
DROP POLICY IF EXISTS "ucr_insert" ON public.user_creation_requests;
CREATE POLICY "ucr_insert"
  ON public.user_creation_requests FOR INSERT
  WITH CHECK (requested_by = auth.uid());

-- Only admins can update (approve / reject)
DROP POLICY IF EXISTS "ucr_admin_update" ON public.user_creation_requests;
CREATE POLICY "ucr_admin_update"
  ON public.user_creation_requests FOR UPDATE
  USING (public.has_role(auth.uid(), 'admin'));

-- Service role (backend) can delete if needed
DROP POLICY IF EXISTS "ucr_service_delete" ON public.user_creation_requests;
CREATE POLICY "ucr_service_delete"
  ON public.user_creation_requests FOR DELETE
  USING (true);

-- ============================================================================
-- END MIGRATION: 20260318000000_user_creation_requests.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260318120000_acord_extraction_workflow.sql
-- ============================================================================
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


-- ============================================================================
-- END MIGRATION: 20260318120000_acord_extraction_workflow.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260318120000_core_schema_gap_closure.sql
-- ============================================================================
-- Core schema gap closure (backward-compatible)
-- Covers:
-- - app_users.role_id + unique email guarantee
-- - roles.role_id + roles.name compatibility columns
-- - devices.tenant_id + devices.token_hash
-- - audit_logs monthly partitioning
-- - strict public.models table
-- - tenants first-class plan/tier columns

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -------------------------------------------------------------------
-- Roles compatibility columns (role_id, name)
-- -------------------------------------------------------------------
ALTER TABLE public.roles
  ADD COLUMN IF NOT EXISTS role_id BIGINT GENERATED BY DEFAULT AS IDENTITY;

ALTER TABLE public.roles
  ADD COLUMN IF NOT EXISTS name TEXT;

UPDATE public.roles
SET name = role::text
WHERE name IS NULL;

UPDATE public.roles
SET role_id = nextval(pg_get_serial_sequence('public.roles', 'role_id'))
WHERE role_id IS NULL;

ALTER TABLE public.roles
  ALTER COLUMN role_id SET NOT NULL;

ALTER TABLE public.roles
  ALTER COLUMN name SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_role_id ON public.roles(role_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_name ON public.roles(name);

-- -------------------------------------------------------------------
-- app_users role_id + unique email at DB level
-- -------------------------------------------------------------------
ALTER TABLE public.app_users
  ADD COLUMN IF NOT EXISTS role_id BIGINT REFERENCES public.roles(role_id) ON DELETE SET NULL;

UPDATE public.app_users au
SET role_id = r.role_id
FROM public.user_roles ur
JOIN public.roles r ON r.role = ur.role
WHERE au.user_id = ur.user_id
  AND au.role_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_app_users_role_id ON public.app_users(role_id);

-- Enforce uniqueness on normalized non-empty emails.
CREATE UNIQUE INDEX IF NOT EXISTS uq_app_users_email_normalized
  ON public.app_users (lower(trim(email)))
  WHERE email IS NOT NULL AND length(trim(email)) > 0;

-- Keep app_users.role_id synchronized from canonical user_roles assignments.
CREATE OR REPLACE FUNCTION public.sync_app_user_role_id_from_user_roles()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  resolved_role_id BIGINT;
BEGIN
  SELECT r.role_id
    INTO resolved_role_id
    FROM public.roles r
   WHERE r.role = NEW.role
   LIMIT 1;

  UPDATE public.app_users au
     SET role_id = resolved_role_id
   WHERE au.user_id = NEW.user_id;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_app_user_role_id_from_user_roles ON public.user_roles;
CREATE TRIGGER trg_sync_app_user_role_id_from_user_roles
  AFTER INSERT OR UPDATE OF role ON public.user_roles
  FOR EACH ROW
  EXECUTE FUNCTION public.sync_app_user_role_id_from_user_roles();

-- -------------------------------------------------------------------
-- Tenants first-class plan/tier columns
-- -------------------------------------------------------------------
ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS plan TEXT,
  ADD COLUMN IF NOT EXISTS tier TEXT;

UPDATE public.tenants
SET plan = COALESCE(NULLIF(metadata ->> 'plan', ''), plan, 'free')
WHERE plan IS NULL;

UPDATE public.tenants
SET tier = COALESCE(NULLIF(metadata ->> 'tier', ''), NULLIF(plan, ''), tier, 'free')
WHERE tier IS NULL;

ALTER TABLE public.tenants
  ALTER COLUMN plan SET DEFAULT 'free',
  ALTER COLUMN tier SET DEFAULT 'free';

ALTER TABLE public.tenants
  ALTER COLUMN plan SET NOT NULL,
  ALTER COLUMN tier SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tenants_plan ON public.tenants(plan);
CREATE INDEX IF NOT EXISTS idx_tenants_tier ON public.tenants(tier);

-- -------------------------------------------------------------------
-- Strict public.models table with version/gpu/memory/manifest
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT NOT NULL DEFAULT '1.0.0',
  gpu TEXT,
  memory TEXT,
  manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_id, version)
);

CREATE INDEX IF NOT EXISTS idx_models_model_id ON public.models(model_id);
CREATE INDEX IF NOT EXISTS idx_models_is_active ON public.models(is_active);

INSERT INTO public.models (model_id, name, version, manifest, is_active)
SELECT
  mc.model_id,
  mc.model_name,
  '1.0.0',
  jsonb_strip_nulls(
    jsonb_build_object(
      'provider', mc.provider,
      'domain', mc.domain,
      'description', mc.description,
      'metadata', COALESCE(mc.metadata, '{}'::jsonb)
    )
  ),
  mc.is_active
FROM public.model_catalog mc
ON CONFLICT (model_id, version) DO UPDATE
SET
  name = EXCLUDED.name,
  manifest = EXCLUDED.manifest,
  is_active = EXCLUDED.is_active;

DROP TRIGGER IF EXISTS update_models_updated_at ON public.models;
CREATE TRIGGER update_models_updated_at
  BEFORE UPDATE ON public.models
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.models ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can view models" ON public.models;
CREATE POLICY "Authenticated users can view models"
  ON public.models
  FOR SELECT
  USING (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS "Admins can manage models" ON public.models;
CREATE POLICY "Admins can manage models"
  ON public.models
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

-- -------------------------------------------------------------------
-- Devices: tenant_id + token_hash compatibility
-- -------------------------------------------------------------------
ALTER TABLE public.devices
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS token_hash TEXT;

UPDATE public.devices d
SET tenant_id = au.tenant_id
FROM public.app_users au
WHERE d.tenant_id IS NULL
  AND d.registered_by = au.user_id;

UPDATE public.devices
SET token_hash = encode(extensions.digest(convert_to(device_token, 'UTF8'), 'sha256'::text), 'hex')
WHERE token_hash IS NULL
  AND device_token IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_devices_tenant_id ON public.devices(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_devices_token_hash
  ON public.devices(token_hash)
  WHERE token_hash IS NOT NULL;

CREATE OR REPLACE FUNCTION public.devices_set_derived_columns()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.device_token IS NOT NULL THEN
    NEW.token_hash := encode(extensions.digest(convert_to(NEW.device_token, 'UTF8'), 'sha256'::text), 'hex');
  END IF;

  IF NEW.tenant_id IS NULL AND NEW.registered_by IS NOT NULL THEN
    SELECT au.tenant_id
      INTO NEW.tenant_id
      FROM public.app_users au
     WHERE au.user_id = NEW.registered_by
     LIMIT 1;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_devices_set_derived_columns ON public.devices;
CREATE TRIGGER trg_devices_set_derived_columns
  BEFORE INSERT OR UPDATE OF device_token, registered_by, tenant_id ON public.devices
  FOR EACH ROW
  EXECUTE FUNCTION public.devices_set_derived_columns();

-- -------------------------------------------------------------------
-- audit_logs monthly partitioning
-- -------------------------------------------------------------------
DO $$
DECLARE
  audit_is_partitioned BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM pg_partitioned_table pt
    JOIN pg_class c ON c.oid = pt.partrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'audit_logs'
  ) INTO audit_is_partitioned;

  IF NOT audit_is_partitioned THEN
    ALTER TABLE public.audit_logs RENAME TO audit_logs_legacy;

    CREATE TABLE public.audit_logs (
      LIKE public.audit_logs_legacy INCLUDING DEFAULTS INCLUDING GENERATED INCLUDING STORAGE INCLUDING COMMENTS EXCLUDING CONSTRAINTS
    ) PARTITION BY RANGE (created_at);

    -- Partitioned tables cannot enforce uniqueness/PK unless partition key is included.
    ALTER TABLE public.audit_logs
      ADD CONSTRAINT audit_logs_pk PRIMARY KEY (created_at, id);

    CREATE TABLE IF NOT EXISTS public.audit_logs_default PARTITION OF public.audit_logs DEFAULT;

    -- Recreate indexes as partitioned indexes on the parent.
    CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON public.audit_logs(user_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_type ON public.audit_logs(resource_type);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_id ON public.audit_logs(id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_id
      ON public.audit_logs(resource_id)
      WHERE resource_id IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_audit_logs_sequence_num
      ON public.audit_logs(sequence_num DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_model_id
      ON public.audit_logs(model_id)
      WHERE model_id IS NOT NULL;

    ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS "Admins can view all audit logs" ON public.audit_logs;
    CREATE POLICY "Admins can view all audit logs"
      ON public.audit_logs
      FOR SELECT
      USING (public.has_role(auth.uid(), 'admin'::public.app_role));

    DROP POLICY IF EXISTS "Users can view own audit logs" ON public.audit_logs;
    CREATE POLICY "Users can view own audit logs"
      ON public.audit_logs
      FOR SELECT
      USING (auth.uid() = user_id);

    DROP POLICY IF EXISTS "Authenticated users can insert own audit logs" ON public.audit_logs;
    CREATE POLICY "Authenticated users can insert own audit logs"
      ON public.audit_logs
      FOR INSERT
      WITH CHECK (
        auth.uid() IS NOT NULL
        AND (
          user_id IS NULL
          OR user_id = auth.uid()
          OR public.has_role(auth.uid(), 'admin'::public.app_role)
        )
      );

    DROP TRIGGER IF EXISTS audit_logs_no_update ON public.audit_logs;
    CREATE TRIGGER audit_logs_no_update
      BEFORE UPDATE ON public.audit_logs
      FOR EACH ROW
      EXECUTE FUNCTION public.prevent_audit_modification();

    DROP TRIGGER IF EXISTS audit_logs_no_delete ON public.audit_logs;
    CREATE TRIGGER audit_logs_no_delete
      BEFORE DELETE ON public.audit_logs
      FOR EACH ROW
      EXECUTE FUNCTION public.prevent_audit_modification();

    DROP TRIGGER IF EXISTS audit_logs_chain_hash ON public.audit_logs;
    CREATE TRIGGER audit_logs_chain_hash
      BEFORE INSERT ON public.audit_logs
      FOR EACH ROW
      EXECUTE FUNCTION public.compute_audit_chain_hash();

    INSERT INTO public.audit_logs
    OVERRIDING SYSTEM VALUE
    SELECT * FROM public.audit_logs_legacy;

    PERFORM setval(
      pg_get_serial_sequence('public.audit_logs', 'sequence_num'),
      COALESCE((SELECT MAX(sequence_num) FROM public.audit_logs), 1),
      true
    );

    DROP TABLE public.audit_logs_legacy;
  END IF;
END;
$$;

-- Create monthly partitions for 12 months back + 24 months forward.
DO $$
DECLARE
  audit_is_partitioned BOOLEAN;
  month_start DATE;
  month_end DATE;
  partition_name TEXT;
  i INTEGER;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM pg_partitioned_table pt
    JOIN pg_class c ON c.oid = pt.partrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'audit_logs'
  ) INTO audit_is_partitioned;

  IF audit_is_partitioned THEN
    FOR i IN -12..24 LOOP
      month_start := (date_trunc('month', CURRENT_DATE) + (i || ' month')::interval)::date;
      month_end := (date_trunc('month', CURRENT_DATE) + ((i + 1) || ' month')::interval)::date;
      partition_name := format('audit_logs_%s', to_char(month_start, 'YYYYMM'));

      EXECUTE format(
        'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.audit_logs FOR VALUES FROM (%L) TO (%L)',
        partition_name,
        month_start,
        month_end
      );
    END LOOP;
  END IF;
END;
$$;

-- ============================================================================
-- END MIGRATION: 20260318120000_core_schema_gap_closure.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260318123000_acord_training_jobs.sql
-- ============================================================================
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


-- ============================================================================
-- END MIGRATION: 20260318123000_acord_training_jobs.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260318124500_strict_tenant_rls_contract.sql
-- ============================================================================
-- Strict tenant-scoped RLS contract with admin/global_admin compatibility.
-- Goals:
-- 1) Keep current admin/global_admin UX behavior.
-- 2) Enforce tenant scoping for admin access (except global_admin override).
-- 3) Align devices policy with JWT tenant claim contract.
-- 4) Make roles metadata readable by tenant admins only.
-- 5) Make audit_logs write path system-only with tenant-admin read scope.

-- -------------------------------------------------------------------
-- Helper functions (safe tenant resolution without RLS recursion)
-- -------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.current_request_user_id()
RETURNS UUID
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_sub TEXT;
BEGIN
  v_sub := COALESCE(current_setting('request.jwt.claim.sub', true), '');
  IF v_sub = '' THEN
    RETURN NULL;
  END IF;
  RETURN v_sub::uuid;
EXCEPTION
  WHEN others THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.jwt_tenant_id()
RETURNS UUID
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_tenant TEXT;
BEGIN
  v_tenant := COALESCE(auth.jwt() ->> 'tenant_id', '');
  IF v_tenant = '' THEN
    RETURN NULL;
  END IF;
  RETURN v_tenant::uuid;
EXCEPTION
  WHEN others THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.current_tenant_id()
RETURNS UUID
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
SET row_security = off
AS $$
DECLARE
  v_tenant UUID;
  v_user_id UUID;
BEGIN
  v_tenant := public.jwt_tenant_id();
  IF v_tenant IS NOT NULL THEN
    RETURN v_tenant;
  END IF;

  v_user_id := public.current_request_user_id();
  IF v_user_id IS NULL THEN
    RETURN NULL;
  END IF;

  SELECT au.tenant_id
    INTO v_tenant
    FROM public.app_users au
   WHERE au.user_id = v_user_id
   LIMIT 1;

  RETURN v_tenant;
END;
$$;

CREATE OR REPLACE FUNCTION public.target_user_in_current_tenant(_target_user UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
SET row_security = off
AS $$
DECLARE
  v_current_tenant UUID;
  v_target_tenant UUID;
BEGIN
  IF _target_user IS NULL THEN
    RETURN FALSE;
  END IF;

  v_current_tenant := public.current_tenant_id();
  IF v_current_tenant IS NULL THEN
    RETURN FALSE;
  END IF;

  SELECT au.tenant_id
    INTO v_target_tenant
    FROM public.app_users au
   WHERE au.user_id = _target_user
   LIMIT 1;

  RETURN v_target_tenant = v_current_tenant;
END;
$$;

-- -------------------------------------------------------------------
-- devices RLS: tenant claim scoped + global_admin override
-- -------------------------------------------------------------------
ALTER TABLE public.devices ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view all devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can manage all devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can insert devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can update devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can delete devices" ON public.devices;
DROP POLICY IF EXISTS "Admins can view devices in own tenant" ON public.devices;
DROP POLICY IF EXISTS "Admins can insert devices in own tenant" ON public.devices;
DROP POLICY IF EXISTS "Admins can update devices in own tenant" ON public.devices;
DROP POLICY IF EXISTS "Admins can delete devices in own tenant" ON public.devices;
DROP POLICY IF EXISTS "Global admins can manage all devices" ON public.devices;

DROP POLICY IF EXISTS "tenant_admins_view_devices" ON public.devices;
CREATE POLICY "tenant_admins_view_devices"
  ON public.devices
  FOR SELECT
  USING (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND tenant_id = public.current_tenant_id()
    )
  );

DROP POLICY IF EXISTS "tenant_admins_insert_devices" ON public.devices;
CREATE POLICY "tenant_admins_insert_devices"
  ON public.devices
  FOR INSERT
  WITH CHECK (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND tenant_id = public.current_tenant_id()
    )
  );

DROP POLICY IF EXISTS "tenant_admins_update_devices" ON public.devices;
CREATE POLICY "tenant_admins_update_devices"
  ON public.devices
  FOR UPDATE
  USING (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND tenant_id = public.current_tenant_id()
    )
  )
  WITH CHECK (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND tenant_id = public.current_tenant_id()
    )
  );

DROP POLICY IF EXISTS "tenant_admins_delete_devices" ON public.devices;
CREATE POLICY "tenant_admins_delete_devices"
  ON public.devices
  FOR DELETE
  USING (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND tenant_id = public.current_tenant_id()
    )
  );

-- -------------------------------------------------------------------
-- app_users RLS: strict tenant scope + self access + global override
-- -------------------------------------------------------------------
ALTER TABLE public.app_users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own app profile" ON public.app_users;
DROP POLICY IF EXISTS "Users can update own app profile" ON public.app_users;
DROP POLICY IF EXISTS "Users can view own app user record" ON public.app_users;
DROP POLICY IF EXISTS "Admins can view all app users" ON public.app_users;
DROP POLICY IF EXISTS "Admins can manage app users" ON public.app_users;
DROP POLICY IF EXISTS "Global admins can manage all app users" ON public.app_users;
DROP POLICY IF EXISTS "Admins can view app users in own tenant" ON public.app_users;
DROP POLICY IF EXISTS "Admins can manage app users in own tenant" ON public.app_users;

DROP POLICY IF EXISTS "app_users_self_select" ON public.app_users;
CREATE POLICY "app_users_self_select"
  ON public.app_users
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "app_users_self_update" ON public.app_users;
CREATE POLICY "app_users_self_update"
  ON public.app_users
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "app_users_tenant_admin_select" ON public.app_users;
CREATE POLICY "app_users_tenant_admin_select"
  ON public.app_users
  FOR SELECT
  USING (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND tenant_id = public.current_tenant_id()
    )
  );

DROP POLICY IF EXISTS "app_users_tenant_admin_manage" ON public.app_users;
CREATE POLICY "app_users_tenant_admin_manage"
  ON public.app_users
  FOR ALL
  USING (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND tenant_id = public.current_tenant_id()
    )
  )
  WITH CHECK (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND tenant_id = public.current_tenant_id()
    )
  );

-- -------------------------------------------------------------------
-- user_roles RLS: tenant admins can manage users in own tenant
-- -------------------------------------------------------------------
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own roles" ON public.user_roles;
DROP POLICY IF EXISTS "Admins can view all user roles" ON public.user_roles;
DROP POLICY IF EXISTS "Admins can manage all user roles" ON public.user_roles;
DROP POLICY IF EXISTS "Admins can insert user roles" ON public.user_roles;
DROP POLICY IF EXISTS "Admins can update user roles" ON public.user_roles;
DROP POLICY IF EXISTS "Admins can delete user roles" ON public.user_roles;
DROP POLICY IF EXISTS "Global admins can manage all user roles" ON public.user_roles;

DROP POLICY IF EXISTS "user_roles_self_select" ON public.user_roles;
CREATE POLICY "user_roles_self_select"
  ON public.user_roles
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_roles_tenant_admin_select" ON public.user_roles;
CREATE POLICY "user_roles_tenant_admin_select"
  ON public.user_roles
  FOR SELECT
  USING (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND public.target_user_in_current_tenant(user_id)
    )
  );

DROP POLICY IF EXISTS "user_roles_tenant_admin_insert" ON public.user_roles;
CREATE POLICY "user_roles_tenant_admin_insert"
  ON public.user_roles
  FOR INSERT
  WITH CHECK (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND public.target_user_in_current_tenant(user_id)
    )
  );

DROP POLICY IF EXISTS "user_roles_tenant_admin_update" ON public.user_roles;
CREATE POLICY "user_roles_tenant_admin_update"
  ON public.user_roles
  FOR UPDATE
  USING (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND public.target_user_in_current_tenant(user_id)
    )
  )
  WITH CHECK (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND public.target_user_in_current_tenant(user_id)
    )
  );

DROP POLICY IF EXISTS "user_roles_tenant_admin_delete" ON public.user_roles;
CREATE POLICY "user_roles_tenant_admin_delete"
  ON public.user_roles
  FOR DELETE
  USING (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND public.target_user_in_current_tenant(user_id)
    )
  );

-- -------------------------------------------------------------------
-- roles metadata RLS: readable by tenant admins/global only
-- -------------------------------------------------------------------
ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can view role metadata" ON public.roles;
DROP POLICY IF EXISTS "Admins can manage role metadata" ON public.roles;

DROP POLICY IF EXISTS "tenant_admins_view_roles_metadata" ON public.roles;
CREATE POLICY "tenant_admins_view_roles_metadata"
  ON public.roles
  FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'::public.app_role));

DROP POLICY IF EXISTS "admins_manage_roles_metadata" ON public.roles;
CREATE POLICY "admins_manage_roles_metadata"
  ON public.roles
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

-- -------------------------------------------------------------------
-- audit_logs RLS: tenant-admin read + system write-only
-- -------------------------------------------------------------------
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL;

UPDATE public.audit_logs al
SET tenant_id = au.tenant_id
FROM public.app_users au
WHERE al.tenant_id IS NULL
  AND al.user_id = au.user_id;

CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON public.audit_logs(tenant_id);

CREATE OR REPLACE FUNCTION public.audit_logs_set_tenant_id()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
SET row_security = off
AS $$
BEGIN
  IF NEW.tenant_id IS NULL AND NEW.user_id IS NOT NULL THEN
    SELECT au.tenant_id
      INTO NEW.tenant_id
      FROM public.app_users au
     WHERE au.user_id = NEW.user_id
     LIMIT 1;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_logs_set_tenant_id ON public.audit_logs;
CREATE TRIGGER trg_audit_logs_set_tenant_id
  BEFORE INSERT ON public.audit_logs
  FOR EACH ROW
  EXECUTE FUNCTION public.audit_logs_set_tenant_id();

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view all audit logs" ON public.audit_logs;
DROP POLICY IF EXISTS "Users can view own audit logs" ON public.audit_logs;
DROP POLICY IF EXISTS "Users can view their own audit logs" ON public.audit_logs;
DROP POLICY IF EXISTS "Authenticated users can insert own audit logs" ON public.audit_logs;
DROP POLICY IF EXISTS "System can insert audit logs" ON public.audit_logs;

DROP POLICY IF EXISTS "tenant_admins_read_audit_logs" ON public.audit_logs;
CREATE POLICY "tenant_admins_read_audit_logs"
  ON public.audit_logs
  FOR SELECT
  USING (
    public.has_role(auth.uid(), 'global_admin'::public.app_role)
    OR (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      AND tenant_id = public.current_tenant_id()
    )
  );

DROP POLICY IF EXISTS "system_write_only_audit_logs" ON public.audit_logs;
-- Backend/service role writes logs; authenticated client writes are blocked.
CREATE POLICY "system_write_only_audit_logs"
  ON public.audit_logs
  FOR INSERT
  WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- END MIGRATION: 20260318124500_strict_tenant_rls_contract.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260318130000_acord_sprint1_fixes.sql
-- ============================================================================
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

-- 3. Eval results table (for Sprint 5 baseline â€” create now so the schema is stable)
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

-- ============================================================================
-- END MIGRATION: 20260318130000_acord_sprint1_fixes.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260318133000_decision_reviews_admin_only_updates.sql
-- ============================================================================
-- Enforce admin/global_admin-only approval/rejection on decision review requests.
-- This removes end-user status updates so only privileged reviewers can decide.

ALTER TABLE public.decision_reviews ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can update own pending reviews" ON public.decision_reviews;

DROP POLICY IF EXISTS "Admins can update reviews" ON public.decision_reviews;
CREATE POLICY "Admins can update reviews"
ON public.decision_reviews FOR UPDATE
USING (public.has_role(auth.uid(), 'admin'::public.app_role))
WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

-- ============================================================================
-- END MIGRATION: 20260318133000_decision_reviews_admin_only_updates.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260318134500_realtime_decision_reviews.sql
-- ============================================================================
-- Enable Supabase Realtime publication for decision review notifications.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'decision_reviews'
  ) AND NOT EXISTS (
    SELECT 1
    FROM pg_publication_rel pr
    JOIN pg_class c ON c.oid = pr.prrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_publication p ON p.oid = pr.prpubid
    WHERE p.pubname = 'supabase_realtime'
      AND n.nspname = 'public'
      AND c.relname = 'decision_reviews'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.decision_reviews;
  END IF;
END $$;

-- ============================================================================
-- END MIGRATION: 20260318134500_realtime_decision_reviews.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260318150000_acord_extraction_feedback_resync.sql
-- ============================================================================
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


-- ============================================================================
-- END MIGRATION: 20260318150000_acord_extraction_feedback_resync.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260319110000_acord_eval_results_unique_job_evalset.sql
-- ============================================================================
-- Ensure idempotent eval persistence: one row per (job_id, eval_set)
ALTER TABLE public.acord_eval_results
  DROP CONSTRAINT IF EXISTS acord_eval_results_job_eval_set_unique;

ALTER TABLE public.acord_eval_results
  ADD CONSTRAINT acord_eval_results_job_eval_set_unique UNIQUE (job_id, eval_set);


-- ============================================================================
-- END MIGRATION: 20260319110000_acord_eval_results_unique_job_evalset.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260320120000_pod_workflow_shared_tables.sql
-- ============================================================================
-- Shared POD extraction workflow:
-- - pod_extraction_runs (user creates, contains extracted_json + raw_text)
-- - pod_extraction_feedback (user/admin corrections)
-- - pod_admin_queue (admin review queue per run)
-- - pod_training_jobs (fine-tuning jobs triggered by admin approval)
-- - pod_eval_results (evaluation metrics persisted per training job)
--
-- This migration is modeled after the existing ACORD tables, but generalized with `pod_id`
-- so the same framework can work for any insurance pod/model/agent.

-- 1) Core run record
CREATE TABLE IF NOT EXISTS public.pod_extraction_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  pod_id TEXT NOT NULL,
  source_filename TEXT,
  source_mime TEXT,

  -- Generic fields: pod extractors may populate these differently.
  raw_text TEXT,
  extracted_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  overall_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,

  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','submitted','needs_admin_review','approved','rejected'))
);

CREATE INDEX IF NOT EXISTS idx_pod_runs_created_by ON public.pod_extraction_runs(created_by);
CREATE INDEX IF NOT EXISTS idx_pod_runs_pod_id ON public.pod_extraction_runs(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_runs_status ON public.pod_extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_pod_runs_created_at ON public.pod_extraction_runs(created_at DESC);

DROP TRIGGER IF EXISTS update_pod_extraction_runs_updated_at ON public.pod_extraction_runs;
CREATE TRIGGER update_pod_extraction_runs_updated_at
  BEFORE UPDATE ON public.pod_extraction_runs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- 2) Feedback/corrections (user + admin)
CREATE TABLE IF NOT EXISTS public.pod_extraction_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  pod_id TEXT NOT NULL,
  run_id UUID NOT NULL REFERENCES public.pod_extraction_runs(id) ON DELETE CASCADE,
  actor_role TEXT NOT NULL CHECK (actor_role IN ('user','admin')),

  thumbs_up BOOLEAN,
  notes TEXT,
  corrected_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_pod_feedback_pod_id ON public.pod_extraction_feedback(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_feedback_run_id ON public.pod_extraction_feedback(run_id);
CREATE INDEX IF NOT EXISTS idx_pod_feedback_created_at ON public.pod_extraction_feedback(created_at DESC);

-- 3) Admin queue (one row per run)
CREATE TABLE IF NOT EXISTS public.pod_admin_queue (
  run_id UUID PRIMARY KEY REFERENCES public.pod_extraction_runs(id) ON DELETE CASCADE,
  pod_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  priority INTEGER NOT NULL DEFAULT 0,
  reason TEXT,
  assigned_to UUID REFERENCES auth.users(id) ON DELETE SET NULL,

  state TEXT NOT NULL DEFAULT 'open'
    CHECK (state IN ('open','in_progress','approved','rework','rejected'))
);

CREATE INDEX IF NOT EXISTS idx_pod_admin_queue_pod_id ON public.pod_admin_queue(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_admin_queue_state ON public.pod_admin_queue(state);
CREATE INDEX IF NOT EXISTS idx_pod_admin_queue_priority ON public.pod_admin_queue(priority DESC);

DROP TRIGGER IF EXISTS update_pod_admin_queue_updated_at ON public.pod_admin_queue;
CREATE TRIGGER update_pod_admin_queue_updated_at
  BEFORE UPDATE ON public.pod_admin_queue
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- 4) Training jobs triggered by admin approval
CREATE TABLE IF NOT EXISTS public.pod_training_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  pod_id TEXT NOT NULL,
  run_id UUID NOT NULL REFERENCES public.pod_extraction_runs(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_pod_training_jobs_pod_id ON public.pod_training_jobs(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_training_jobs_run_id ON public.pod_training_jobs(run_id);
CREATE INDEX IF NOT EXISTS idx_pod_training_jobs_status ON public.pod_training_jobs(status);
CREATE INDEX IF NOT EXISTS idx_pod_training_jobs_created_at ON public.pod_training_jobs(created_at DESC);

DROP TRIGGER IF EXISTS update_pod_training_jobs_updated_at ON public.pod_training_jobs;
CREATE TRIGGER update_pod_training_jobs_updated_at
  BEFORE UPDATE ON public.pod_training_jobs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.pod_extraction_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_extraction_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_admin_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pod_training_jobs ENABLE ROW LEVEL SECURITY;

-- 5) Evaluation results persisted per training job
CREATE TABLE IF NOT EXISTS public.pod_eval_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  pod_id TEXT NOT NULL,
  job_id UUID REFERENCES public.pod_training_jobs(id) ON DELETE SET NULL,

  eval_set TEXT NOT NULL CHECK (eval_set IN ('seen','paraphrased','oos','combined')),

  exact_match DOUBLE PRECISION,
  soft_accuracy DOUBLE PRECISION,
  semantic_sim DOUBLE PRECISION,
  hallucination_rate DOUBLE PRECISION,
  refusal_rate DOUBLE PRECISION,

  metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_pod_eval_results_pod_id ON public.pod_eval_results(pod_id);
CREATE INDEX IF NOT EXISTS idx_pod_eval_results_job_id ON public.pod_eval_results(job_id);
CREATE INDEX IF NOT EXISTS idx_pod_eval_results_created_at ON public.pod_eval_results(created_at DESC);

ALTER TABLE public.pod_eval_results ENABLE ROW LEVEL SECURITY;

-- -------------------------
-- RLS policies (mirroring ACORD)
-- -------------------------

-- pod_extraction_runs policies
DROP POLICY IF EXISTS "Users can insert own pod runs" ON public.pod_extraction_runs;
CREATE POLICY "Users can insert own pod runs"
  ON public.pod_extraction_runs
  FOR INSERT
  WITH CHECK (auth.uid() = created_by);

DROP POLICY IF EXISTS "Users can view own pod runs" ON public.pod_extraction_runs;
CREATE POLICY "Users can view own pod runs"
  ON public.pod_extraction_runs
  FOR SELECT
  USING (auth.uid() = created_by);

DROP POLICY IF EXISTS "Users can update own draft pod runs" ON public.pod_extraction_runs;
CREATE POLICY "Users can update own draft pod runs"
  ON public.pod_extraction_runs
  FOR UPDATE
  USING (auth.uid() = created_by AND status IN ('draft','submitted'))
  WITH CHECK (auth.uid() = created_by);

DROP POLICY IF EXISTS "Admins can manage all pod runs" ON public.pod_extraction_runs;
CREATE POLICY "Admins can manage all pod runs"
  ON public.pod_extraction_runs
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- pod_extraction_feedback policies
DROP POLICY IF EXISTS "Users can insert feedback for own pod runs" ON public.pod_extraction_feedback;
CREATE POLICY "Users can insert feedback for own pod runs"
  ON public.pod_extraction_feedback
  FOR INSERT
  WITH CHECK (
    auth.uid() = created_by
    AND (
      EXISTS (
        SELECT 1
        FROM public.pod_extraction_runs r
        WHERE r.id = run_id
          AND r.created_by = auth.uid()
          AND r.pod_id = pod_id
      )
      OR public.has_role(auth.uid(), 'admin')
    )
  );

DROP POLICY IF EXISTS "Users can view feedback for own pod runs" ON public.pod_extraction_feedback;
CREATE POLICY "Users can view feedback for own pod runs"
  ON public.pod_extraction_feedback
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1
      FROM public.pod_extraction_runs r
      WHERE r.id = run_id
        AND r.created_by = auth.uid()
        AND r.pod_id = pod_id
    )
    OR public.has_role(auth.uid(), 'admin')
  );

DROP POLICY IF EXISTS "Admins can manage all pod feedback" ON public.pod_extraction_feedback;
CREATE POLICY "Admins can manage all pod feedback"
  ON public.pod_extraction_feedback
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- pod_admin_queue policies
DROP POLICY IF EXISTS "Admins can manage pod admin queue" ON public.pod_admin_queue;
CREATE POLICY "Admins can manage pod admin queue"
  ON public.pod_admin_queue
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- pod_training_jobs policies
DROP POLICY IF EXISTS "Users can view own pod training jobs" ON public.pod_training_jobs;
CREATE POLICY "Users can view own pod training jobs"
  ON public.pod_training_jobs
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1
      FROM public.pod_extraction_runs r
      WHERE r.id = pod_training_jobs.run_id
        AND r.created_by = auth.uid()
        AND r.pod_id = pod_training_jobs.pod_id
    )
    OR public.has_role(auth.uid(), 'admin')
  );

DROP POLICY IF EXISTS "Admins can manage pod training jobs" ON public.pod_training_jobs;
CREATE POLICY "Admins can manage pod training jobs"
  ON public.pod_training_jobs
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- pod_eval_results policies
DROP POLICY IF EXISTS "Admins can manage pod eval results" ON public.pod_eval_results;
CREATE POLICY "Admins can manage pod eval results"
  ON public.pod_eval_results
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- Constraints for idempotent inserts
-- (Keep history immutable: one eval result row per (job_id, eval_set))
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'pod_eval_results_job_evalset_unique'
  ) THEN
    ALTER TABLE public.pod_eval_results
      ADD CONSTRAINT pod_eval_results_job_evalset_unique UNIQUE (job_id, eval_set);
  END IF;
END
$$;

-- Prevent duplicate training jobs for the same run by default.
-- Note: the runner may create a NEW job row for restarts; the simplest safe behavior is
-- to keep UNIQUE(run_id) like ACORD does today.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'pod_training_jobs_run_id_unique'
  ) THEN
    ALTER TABLE public.pod_training_jobs
      ADD CONSTRAINT pod_training_jobs_run_id_unique UNIQUE (run_id);
  END IF;
END
$$;


-- ============================================================================
-- END MIGRATION: 20260320120000_pod_workflow_shared_tables.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260323120000_pod_workflow_history_and_original_json.sql
-- ============================================================================
-- Pod workflow hardening:
-- 1) Keep immutable original extraction JSON for each run.
-- 2) Allow multiple training jobs per run so retry/retrain history is preserved.

ALTER TABLE public.pod_extraction_runs
  ADD COLUMN IF NOT EXISTS original_extracted_json JSONB;

-- Backfill for existing rows.
UPDATE public.pod_extraction_runs
SET original_extracted_json = COALESCE(original_extracted_json, extracted_json, '{}'::jsonb)
WHERE original_extracted_json IS NULL;

ALTER TABLE public.pod_extraction_runs
  ALTER COLUMN original_extracted_json SET DEFAULT '{}'::jsonb;

-- Remove UNIQUE(run_id) so each rerun can create a new history row.
ALTER TABLE public.pod_training_jobs
  DROP CONSTRAINT IF EXISTS pod_training_jobs_run_id_unique;


-- ============================================================================
-- END MIGRATION: 20260323120000_pod_workflow_history_and_original_json.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260323123000_acord_original_json_history.sql
-- ============================================================================
-- ACORD workflow parity with generic pod workflow:
-- preserve immutable original extraction JSON for side-by-side review.

ALTER TABLE public.acord_extraction_runs
  ADD COLUMN IF NOT EXISTS original_extracted_json JSONB;

UPDATE public.acord_extraction_runs
SET original_extracted_json = COALESCE(original_extracted_json, extracted_json, '{}'::jsonb)
WHERE original_extracted_json IS NULL;

ALTER TABLE public.acord_extraction_runs
  ALTER COLUMN original_extracted_json SET DEFAULT '{}'::jsonb;


-- ============================================================================
-- END MIGRATION: 20260323123000_acord_original_json_history.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260323170000_app_users_password_change_timestamp.sql
-- ============================================================================
-- Track when a user last changed their password.
-- Keeps both a first-class timestamp column and compatibility metadata key.

ALTER TABLE public.app_users
  ADD COLUMN IF NOT EXISTS last_password_changed_at TIMESTAMPTZ;

-- Backfill from metadata key where available and parseable.
UPDATE public.app_users
SET last_password_changed_at = (metadata ->> 'password_updated_at')::timestamptz
WHERE last_password_changed_at IS NULL
  AND metadata ? 'password_updated_at'
  AND (metadata ->> 'password_updated_at') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T';

CREATE INDEX IF NOT EXISTS idx_app_users_last_password_changed_at
  ON public.app_users(last_password_changed_at DESC);

-- ============================================================================
-- END MIGRATION: 20260323170000_app_users_password_change_timestamp.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260324093000_user_notifications_inbox.sql
-- ============================================================================
-- Persistent per-user realtime notification inbox for bell + read/clear state.

create table if not exists public.user_notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  table_name text not null check (table_name in ('pod_activation_requests', 'device_sync_logs', 'decision_reviews')),
  event_type text not null check (event_type in ('INSERT', 'UPDATE', 'DELETE')),
  message text not null,
  target_path text null,
  source_fingerprint text not null,
  created_at timestamptz not null default now(),
  read_at timestamptz null
);

create index if not exists idx_user_notifications_user_created
  on public.user_notifications (user_id, created_at desc);

create index if not exists idx_user_notifications_user_unread
  on public.user_notifications (user_id, read_at);

create index if not exists idx_user_notifications_dedupe
  on public.user_notifications (user_id, source_fingerprint, created_at desc);

alter table public.user_notifications enable row level security;

drop policy if exists "user_notifications_select_own" on public.user_notifications;
create policy "user_notifications_select_own"
  on public.user_notifications
  for select
  using (auth.uid() = user_id);

drop policy if exists "user_notifications_insert_own" on public.user_notifications;
create policy "user_notifications_insert_own"
  on public.user_notifications
  for insert
  with check (auth.uid() = user_id);

drop policy if exists "user_notifications_update_own" on public.user_notifications;
create policy "user_notifications_update_own"
  on public.user_notifications
  for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "user_notifications_delete_own" on public.user_notifications;
create policy "user_notifications_delete_own"
  on public.user_notifications
  for delete
  using (auth.uid() = user_id);

-- ============================================================================
-- END MIGRATION: 20260324093000_user_notifications_inbox.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260324183000_tenant_isolation_enforcement.sql
-- ============================================================================
-- Enforce strict tenant isolation for admin/global_admin access paths.
-- Goal: tenant users must never see/manage other-tenant users/devices/activity/requests.

-- -------------------------------------------------------------------
-- devices: ensure tenant_id exists for policy filters
-- -------------------------------------------------------------------
ALTER TABLE public.devices
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL;

UPDATE public.devices d
SET tenant_id = au.tenant_id
FROM public.app_users au
WHERE d.tenant_id IS NULL
  AND d.registered_by IS NOT NULL
  AND au.user_id = d.registered_by;

CREATE INDEX IF NOT EXISTS idx_devices_tenant_id ON public.devices(tenant_id);

-- -------------------------------------------------------------------
-- user_creation_requests: add tenant ownership
-- -------------------------------------------------------------------
ALTER TABLE public.user_creation_requests
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL;

UPDATE public.user_creation_requests ucr
SET tenant_id = au.tenant_id
FROM public.app_users au
WHERE ucr.tenant_id IS NULL
  AND au.user_id = ucr.requested_by;

CREATE INDEX IF NOT EXISTS idx_ucr_tenant_status
  ON public.user_creation_requests (tenant_id, status, created_at DESC);

-- -------------------------------------------------------------------
-- app_users RLS: tenant-only for admins/global_admin (plus self)
-- -------------------------------------------------------------------
ALTER TABLE public.app_users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "app_users_tenant_admin_select" ON public.app_users;
CREATE POLICY "app_users_tenant_admin_select"
  ON public.app_users
  FOR SELECT
  USING (
    auth.uid() = user_id
    OR (
      (
        public.has_role(auth.uid(), 'admin'::public.app_role)
        OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
      )
      AND tenant_id = public.current_tenant_id()
    )
  );

DROP POLICY IF EXISTS "app_users_tenant_admin_manage" ON public.app_users;
CREATE POLICY "app_users_tenant_admin_manage"
  ON public.app_users
  FOR ALL
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  )
  WITH CHECK (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

-- -------------------------------------------------------------------
-- user_roles RLS: tenant-only role management
-- -------------------------------------------------------------------
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_roles_tenant_admin_select" ON public.user_roles;
CREATE POLICY "user_roles_tenant_admin_select"
  ON public.user_roles
  FOR SELECT
  USING (
    auth.uid() = user_id
    OR (
      (
        public.has_role(auth.uid(), 'admin'::public.app_role)
        OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
      )
      AND public.target_user_in_current_tenant(user_id)
    )
  );

DROP POLICY IF EXISTS "user_roles_tenant_admin_insert" ON public.user_roles;
CREATE POLICY "user_roles_tenant_admin_insert"
  ON public.user_roles
  FOR INSERT
  WITH CHECK (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND public.target_user_in_current_tenant(user_id)
  );

DROP POLICY IF EXISTS "user_roles_tenant_admin_update" ON public.user_roles;
CREATE POLICY "user_roles_tenant_admin_update"
  ON public.user_roles
  FOR UPDATE
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND public.target_user_in_current_tenant(user_id)
  )
  WITH CHECK (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND public.target_user_in_current_tenant(user_id)
  );

DROP POLICY IF EXISTS "user_roles_tenant_admin_delete" ON public.user_roles;
CREATE POLICY "user_roles_tenant_admin_delete"
  ON public.user_roles
  FOR DELETE
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND public.target_user_in_current_tenant(user_id)
  );

-- -------------------------------------------------------------------
-- devices RLS: tenant-only visibility/manage for admins/global_admin
-- -------------------------------------------------------------------
ALTER TABLE public.devices ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_admins_view_devices" ON public.devices;
CREATE POLICY "tenant_admins_view_devices"
  ON public.devices
  FOR SELECT
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

DROP POLICY IF EXISTS "tenant_admins_insert_devices" ON public.devices;
CREATE POLICY "tenant_admins_insert_devices"
  ON public.devices
  FOR INSERT
  WITH CHECK (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

DROP POLICY IF EXISTS "tenant_admins_update_devices" ON public.devices;
CREATE POLICY "tenant_admins_update_devices"
  ON public.devices
  FOR UPDATE
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  )
  WITH CHECK (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

DROP POLICY IF EXISTS "tenant_admins_delete_devices" ON public.devices;
CREATE POLICY "tenant_admins_delete_devices"
  ON public.devices
  FOR DELETE
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

-- -------------------------------------------------------------------
-- audit_logs RLS: tenant-only for admin/global_admin; self-only for users
-- -------------------------------------------------------------------
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_admins_read_audit_logs" ON public.audit_logs;
CREATE POLICY "tenant_admins_read_audit_logs"
  ON public.audit_logs
  FOR SELECT
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

DROP POLICY IF EXISTS "users_view_own_audit_logs" ON public.audit_logs;
CREATE POLICY "users_view_own_audit_logs"
  ON public.audit_logs
  FOR SELECT
  USING (auth.uid() = user_id);

-- Keep system write-only policy intact.

-- -------------------------------------------------------------------
-- user_creation_requests RLS: tenant-only queues
-- -------------------------------------------------------------------
ALTER TABLE public.user_creation_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "ucr_requester_select" ON public.user_creation_requests;
CREATE POLICY "ucr_requester_select"
  ON public.user_creation_requests FOR SELECT
  USING (requested_by = auth.uid());

DROP POLICY IF EXISTS "ucr_admin_select" ON public.user_creation_requests;
CREATE POLICY "ucr_admin_select"
  ON public.user_creation_requests FOR SELECT
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

DROP POLICY IF EXISTS "ucr_insert" ON public.user_creation_requests;
CREATE POLICY "ucr_insert"
  ON public.user_creation_requests FOR INSERT
  WITH CHECK (
    requested_by = auth.uid()
    AND tenant_id = public.current_tenant_id()
  );

DROP POLICY IF EXISTS "ucr_admin_update" ON public.user_creation_requests;
CREATE POLICY "ucr_admin_update"
  ON public.user_creation_requests FOR UPDATE
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  )
  WITH CHECK (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

-- ============================================================================
-- END MIGRATION: 20260324183000_tenant_isolation_enforcement.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260326120000_pod_activation_tenant_scope.sql
-- ============================================================================
-- Tenant-scope pod activation requests for reliable isolation and admin review UX.

ALTER TABLE public.pod_activation_requests
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL;

-- Backfill tenant ownership from requester profile.
UPDATE public.pod_activation_requests par
SET tenant_id = au.tenant_id
FROM public.app_users au
WHERE par.tenant_id IS NULL
  AND par.user_id = au.user_id;

CREATE INDEX IF NOT EXISTS idx_par_tenant_status_requested
  ON public.pod_activation_requests (tenant_id, status, requested_at DESC);

ALTER TABLE public.pod_activation_requests ENABLE ROW LEVEL SECURITY;

-- Requesters can see their own rows in their tenant.
DROP POLICY IF EXISTS "Users can view their own requests" ON public.pod_activation_requests;
CREATE POLICY "Users can view their own requests"
ON public.pod_activation_requests FOR SELECT
USING (
  auth.uid() = user_id
  AND tenant_id = public.current_tenant_id()
);

-- Requesters can create rows only for themselves in their tenant.
DROP POLICY IF EXISTS "Users can create activation requests" ON public.pod_activation_requests;
CREATE POLICY "Users can create activation requests"
ON public.pod_activation_requests FOR INSERT
WITH CHECK (
  auth.uid() = user_id
  AND tenant_id = public.current_tenant_id()
);

-- Tenant admins/global_admin can view tenant queue.
DROP POLICY IF EXISTS "Admins can view all requests" ON public.pod_activation_requests;
CREATE POLICY "Admins can view all requests"
ON public.pod_activation_requests FOR SELECT
USING (
  (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
  )
  AND tenant_id = public.current_tenant_id()
);

-- Tenant admins/global_admin can update only tenant rows.
DROP POLICY IF EXISTS "Admins can update requests" ON public.pod_activation_requests;
CREATE POLICY "Admins can update requests"
ON public.pod_activation_requests FOR UPDATE
USING (
  (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
  )
  AND tenant_id = public.current_tenant_id()
)
WITH CHECK (
  (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
  )
  AND tenant_id = public.current_tenant_id()
);

-- Users can cancel only own pending requests in their tenant.
DROP POLICY IF EXISTS "Users can cancel pending requests" ON public.pod_activation_requests;
CREATE POLICY "Users can cancel pending requests"
ON public.pod_activation_requests FOR DELETE
USING (
  auth.uid() = user_id
  AND status = 'pending'
  AND tenant_id = public.current_tenant_id()
);

-- ============================================================================
-- END MIGRATION: 20260326120000_pod_activation_tenant_scope.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260327100000_tenant_name_canonicalization.sql
-- ============================================================================
-- Canonicalize tenant identity by normalized tenant name.
-- Goal: users/devices/requests created with the same tenant name must map to one tenant_id.

-- -------------------------------------------------------------------
-- 1) Merge duplicate active tenants by normalized name (case-insensitive)
-- -------------------------------------------------------------------
WITH ranked AS (
  SELECT
    id,
    lower(trim(name)) AS norm_name,
    created_at,
    ROW_NUMBER() OVER (PARTITION BY lower(trim(name)) ORDER BY created_at ASC, id ASC) AS rn
  FROM public.tenants
  WHERE is_active = true
),
mapping AS (
  SELECT d.id AS duplicate_id, c.id AS canonical_id, d.norm_name
  FROM ranked d
  JOIN ranked c
    ON c.norm_name = d.norm_name
   AND c.rn = 1
  WHERE d.rn > 1
)
UPDATE public.app_users au
SET tenant_id = m.canonical_id
FROM mapping m
WHERE au.tenant_id = m.duplicate_id;

WITH ranked AS (
  SELECT
    id,
    lower(trim(name)) AS norm_name,
    created_at,
    ROW_NUMBER() OVER (PARTITION BY lower(trim(name)) ORDER BY created_at ASC, id ASC) AS rn
  FROM public.tenants
  WHERE is_active = true
),
mapping AS (
  SELECT d.id AS duplicate_id, c.id AS canonical_id
  FROM ranked d
  JOIN ranked c
    ON c.norm_name = d.norm_name
   AND c.rn = 1
  WHERE d.rn > 1
)
UPDATE public.devices dv
SET tenant_id = m.canonical_id
FROM mapping m
WHERE dv.tenant_id = m.duplicate_id;

WITH ranked AS (
  SELECT
    id,
    lower(trim(name)) AS norm_name,
    created_at,
    ROW_NUMBER() OVER (PARTITION BY lower(trim(name)) ORDER BY created_at ASC, id ASC) AS rn
  FROM public.tenants
  WHERE is_active = true
),
mapping AS (
  SELECT d.id AS duplicate_id, c.id AS canonical_id
  FROM ranked d
  JOIN ranked c
    ON c.norm_name = d.norm_name
   AND c.rn = 1
  WHERE d.rn > 1
)
UPDATE public.user_creation_requests ucr
SET tenant_id = m.canonical_id
FROM mapping m
WHERE ucr.tenant_id = m.duplicate_id;

WITH ranked AS (
  SELECT
    id,
    lower(trim(name)) AS norm_name,
    created_at,
    ROW_NUMBER() OVER (PARTITION BY lower(trim(name)) ORDER BY created_at ASC, id ASC) AS rn
  FROM public.tenants
  WHERE is_active = true
),
mapping AS (
  SELECT d.id AS duplicate_id, c.id AS canonical_id
  FROM ranked d
  JOIN ranked c
    ON c.norm_name = d.norm_name
   AND c.rn = 1
  WHERE d.rn > 1
)
UPDATE public.audit_logs al
SET tenant_id = m.canonical_id
FROM mapping m
WHERE al.tenant_id = m.duplicate_id;

WITH ranked AS (
  SELECT
    id,
    lower(trim(name)) AS norm_name,
    created_at,
    ROW_NUMBER() OVER (PARTITION BY lower(trim(name)) ORDER BY created_at ASC, id ASC) AS rn
  FROM public.tenants
  WHERE is_active = true
),
mapping AS (
  SELECT d.id AS duplicate_id, c.id AS canonical_id
  FROM ranked d
  JOIN ranked c
    ON c.norm_name = d.norm_name
   AND c.rn = 1
  WHERE d.rn > 1
)
UPDATE public.pod_activation_requests par
SET tenant_id = m.canonical_id
FROM mapping m
WHERE par.tenant_id = m.duplicate_id;

-- Mark duplicates inactive (preserve history, prevent future accidental use).
WITH ranked AS (
  SELECT
    id,
    lower(trim(name)) AS norm_name,
    created_at,
    ROW_NUMBER() OVER (PARTITION BY lower(trim(name)) ORDER BY created_at ASC, id ASC) AS rn
  FROM public.tenants
  WHERE is_active = true
),
mapping AS (
  SELECT d.id AS duplicate_id, c.id AS canonical_id
  FROM ranked d
  JOIN ranked c
    ON c.norm_name = d.norm_name
   AND c.rn = 1
  WHERE d.rn > 1
)
UPDATE public.tenants t
SET
  is_active = false,
  metadata = COALESCE(t.metadata, '{}'::jsonb) || jsonb_build_object(
    'merged_into_tenant_id', m.canonical_id,
    'merged_at', now()
  )
FROM mapping m
WHERE t.id = m.duplicate_id;

-- Enforce one active tenant row per normalized name.
CREATE UNIQUE INDEX IF NOT EXISTS uq_tenants_active_norm_name
  ON public.tenants ((lower(trim(name))))
  WHERE is_active = true;

-- -------------------------------------------------------------------
-- 2) Update signup trigger: reuse existing active tenant by name
-- -------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_new_app_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  default_tenant_id UUID;
  resolved_tenant_id UUID;
  requested_tenant_name TEXT;
  requested_plan TEXT;
  requested_role TEXT;
  requested_signup_version TEXT;
  requested_model_id TEXT;
  requested_device_name TEXT;
  requested_device_profile JSONB;
  normalized_slug TEXT;
  generated_slug TEXT;
  resolved_model_name TEXT;
  resolved_domain public.model_domain;
BEGIN
  requested_tenant_name := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'tenant_name', '')), '');
  requested_plan := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'plan', '')), '');
  requested_role := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'requested_role', '')), '');
  requested_signup_version := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'signup_wizard_version', '')), '');
  requested_model_id := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'default_model_id', '')), '');
  requested_device_name := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'device_name', '')), '');
  requested_device_profile := COALESCE(NEW.raw_user_meta_data -> 'device_profile', '{}'::jsonb);
  IF requested_device_name IS NULL THEN
    requested_device_name := NULLIF(trim(COALESCE(requested_device_profile ->> 'device_name', '')), '');
  END IF;

  SELECT id INTO default_tenant_id
  FROM public.tenants
  WHERE slug = 'default-tenant'
  LIMIT 1;

  resolved_tenant_id := default_tenant_id;

  IF requested_tenant_name IS NOT NULL THEN
    -- Reuse existing active tenant with same normalized name.
    SELECT id INTO resolved_tenant_id
    FROM public.tenants
    WHERE is_active = true
      AND lower(trim(name)) = lower(trim(requested_tenant_name))
    ORDER BY created_at ASC, id ASC
    LIMIT 1;

    IF resolved_tenant_id IS NULL THEN
      normalized_slug := lower(regexp_replace(requested_tenant_name, '[^a-zA-Z0-9]+', '-', 'g'));
      normalized_slug := trim(both '-' FROM normalized_slug);
      IF normalized_slug = '' THEN
        normalized_slug := 'tenant';
      END IF;

      generated_slug := normalized_slug || '-' || substring(replace(NEW.id::text, '-', ''), 1, 8);

      INSERT INTO public.tenants (slug, name, is_active, metadata)
      VALUES (
        generated_slug,
        requested_tenant_name,
        true,
        jsonb_strip_nulls(
          jsonb_build_object(
            'created_from_signup', true,
            'signup_user_id', NEW.id,
            'plan', requested_plan
          )
        )
      )
      ON CONFLICT (slug) DO UPDATE
      SET
        name = EXCLUDED.name,
        metadata = COALESCE(public.tenants.metadata, '{}'::jsonb) || EXCLUDED.metadata
      RETURNING id INTO resolved_tenant_id;
    END IF;
  END IF;

  INSERT INTO public.app_users (user_id, email, full_name, tenant_id, status, metadata)
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    NULLIF(NEW.raw_user_meta_data ->> 'full_name', ''),
    resolved_tenant_id,
    'active',
    jsonb_strip_nulls(
      jsonb_build_object(
        'onboarding_plan', requested_plan,
        'onboarding_requested_role', requested_role,
        'onboarding_signup_wizard_version', requested_signup_version,
        'onboarding_default_model_id', requested_model_id,
        'onboarding_device_name', requested_device_name,
        'onboarding_tenant_name', requested_tenant_name,
        'onboarding_device_profile', requested_device_profile
      )
    )
  )
  ON CONFLICT (user_id) DO UPDATE
  SET
    email = EXCLUDED.email,
    full_name = COALESCE(EXCLUDED.full_name, public.app_users.full_name),
    tenant_id = COALESCE(EXCLUDED.tenant_id, public.app_users.tenant_id),
    metadata = COALESCE(public.app_users.metadata, '{}'::jsonb) || EXCLUDED.metadata;

  IF requested_model_id IS NOT NULL THEN
    SELECT mc.model_name, mc.domain::public.model_domain
      INTO resolved_model_name, resolved_domain
    FROM public.model_catalog mc
    WHERE mc.model_id = requested_model_id
      AND mc.is_active = true
    LIMIT 1;

    IF resolved_model_name IS NULL THEN
      resolved_model_name := CASE requested_model_id
        WHEN 'quote-generation' THEN 'Quote Generation Agent'
        WHEN 'policy-comparison' THEN 'Policy Comparison Engine'
        WHEN 'document-retrieval' THEN 'Document Retrieval'
        WHEN 'claims-fnol' THEN 'Claims and FNOL Intelligence'
        WHEN 'coverage-validation' THEN 'Coverage Validation and Eligibility'
        ELSE initcap(replace(requested_model_id, '-', ' '))
      END;
    END IF;

    IF resolved_domain IS NULL THEN
      resolved_domain := 'insurance'::public.model_domain;
    END IF;

    INSERT INTO public.activated_models (user_id, model_id, model_name, domain)
    VALUES (NEW.id, requested_model_id, resolved_model_name, resolved_domain)
    ON CONFLICT (user_id, model_id) DO NOTHING;
  END IF;

  IF requested_device_name IS NOT NULL THEN
    INSERT INTO public.devices (device_name, device_token, registered_by, tenant_id, status, os_type, app_version, metadata)
    VALUES (
      requested_device_name,
      public.generate_device_token(),
      NEW.id,
      resolved_tenant_id,
      'never_checked_in',
      NULLIF(requested_device_profile ->> 'os_name', ''),
      NULLIF(requested_device_profile ->> 'app_version', ''),
      jsonb_strip_nulls(
        jsonb_build_object(
          'created_from_signup', true,
          'signup_user_id', NEW.id,
          'device_profile', requested_device_profile
        )
      )
    );
  END IF;

  RETURN NEW;
END;
$$;

-- ============================================================================
-- END MIGRATION: 20260327100000_tenant_name_canonicalization.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260327113000_decision_reviews_tenant_scope.sql
-- ============================================================================
-- Enforce tenant-scoped isolation for decision_reviews.

ALTER TABLE public.decision_reviews
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL;

-- Backfill tenant ownership from requester profile.
UPDATE public.decision_reviews dr
SET tenant_id = au.tenant_id
FROM public.app_users au
WHERE dr.tenant_id IS NULL
  AND dr.user_id = au.user_id;

CREATE INDEX IF NOT EXISTS idx_decision_reviews_tenant_status_created
  ON public.decision_reviews (tenant_id, status, created_at DESC);

ALTER TABLE public.decision_reviews ENABLE ROW LEVEL SECURITY;

-- Replace legacy broad policies with tenant-scoped policies.
DROP POLICY IF EXISTS "Users can view their own reviews" ON public.decision_reviews;
DROP POLICY IF EXISTS "Users can create reviews" ON public.decision_reviews;
DROP POLICY IF EXISTS "Admins can view all reviews" ON public.decision_reviews;
DROP POLICY IF EXISTS "Admins can update reviews" ON public.decision_reviews;
DROP POLICY IF EXISTS "Users can update own pending reviews" ON public.decision_reviews;

CREATE POLICY "Users can view their own reviews"
ON public.decision_reviews FOR SELECT
USING (
  auth.uid() = user_id
  AND tenant_id = public.current_tenant_id()
);

CREATE POLICY "Users can create reviews"
ON public.decision_reviews FOR INSERT
WITH CHECK (
  auth.uid() = user_id
  AND tenant_id = public.current_tenant_id()
);

CREATE POLICY "Admins can view tenant reviews"
ON public.decision_reviews FOR SELECT
USING (
  (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
  )
  AND tenant_id = public.current_tenant_id()
);

CREATE POLICY "Admins can update tenant reviews"
ON public.decision_reviews FOR UPDATE
USING (
  (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
  )
  AND tenant_id = public.current_tenant_id()
)
WITH CHECK (
  (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
  )
  AND tenant_id = public.current_tenant_id()
);

-- ============================================================================
-- END MIGRATION: 20260327113000_decision_reviews_tenant_scope.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260327120000_auth_audit_tenant_scope.sql
-- ============================================================================
-- Tenant-scope auth_audit visibility for admin/global_admin.

ALTER TABLE public.auth_audit
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL;

-- Backfill tenant ownership from app_users.
-- auth_audit is immutable by trigger, so temporarily disable only the UPDATE guard.
ALTER TABLE public.auth_audit DISABLE TRIGGER auth_audit_no_update;
UPDATE public.auth_audit aa
SET tenant_id = au.tenant_id
FROM public.app_users au
WHERE aa.tenant_id IS NULL
  AND aa.user_id = au.user_id;
ALTER TABLE public.auth_audit ENABLE TRIGGER auth_audit_no_update;

CREATE INDEX IF NOT EXISTS idx_auth_audit_tenant_created
  ON public.auth_audit (tenant_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.auth_audit_set_tenant_id()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.tenant_id IS NULL AND NEW.user_id IS NOT NULL THEN
    SELECT au.tenant_id
      INTO NEW.tenant_id
    FROM public.app_users au
    WHERE au.user_id = NEW.user_id
    LIMIT 1;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_auth_audit_set_tenant_id ON public.auth_audit;
CREATE TRIGGER trg_auth_audit_set_tenant_id
  BEFORE INSERT
  ON public.auth_audit
  FOR EACH ROW
  EXECUTE FUNCTION public.auth_audit_set_tenant_id();

ALTER TABLE public.auth_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can insert their own auth audit" ON public.auth_audit;
CREATE POLICY "Users can insert their own auth audit"
ON public.auth_audit
FOR INSERT
WITH CHECK (
  auth.uid() = user_id
  AND tenant_id = public.current_tenant_id()
);

DROP POLICY IF EXISTS "Users see own auth audit" ON public.auth_audit;
CREATE POLICY "Users see own auth audit"
ON public.auth_audit
FOR SELECT
USING (
  user_id = auth.uid()
  AND tenant_id = public.current_tenant_id()
);

DROP POLICY IF EXISTS "Admins see all except global_admin auth audit" ON public.auth_audit;
DROP POLICY IF EXISTS "Admins see user+admin auth audit" ON public.auth_audit;
CREATE POLICY "Admins see tenant auth audit"
ON public.auth_audit
FOR SELECT
USING (
  (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
  )
  AND tenant_id = public.current_tenant_id()
);

DROP POLICY IF EXISTS "Global admins see all auth audit" ON public.auth_audit;

-- ============================================================================
-- END MIGRATION: 20260327120000_auth_audit_tenant_scope.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260327123000_device_sync_logs_tenant_scope.sql
-- ============================================================================
-- Tenant-scope device sync logs for notification isolation.

ALTER TABLE public.device_sync_logs
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL;

-- Backfill from owning device.
UPDATE public.device_sync_logs dsl
SET tenant_id = d.tenant_id
FROM public.devices d
WHERE dsl.tenant_id IS NULL
  AND dsl.device_id = d.id;

CREATE INDEX IF NOT EXISTS idx_device_sync_logs_tenant_created
  ON public.device_sync_logs (tenant_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.device_sync_logs_set_tenant_id()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.tenant_id IS NULL AND NEW.device_id IS NOT NULL THEN
    SELECT d.tenant_id
      INTO NEW.tenant_id
    FROM public.devices d
    WHERE d.id = NEW.device_id
    LIMIT 1;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_device_sync_logs_set_tenant_id ON public.device_sync_logs;
CREATE TRIGGER trg_device_sync_logs_set_tenant_id
  BEFORE INSERT OR UPDATE OF device_id, tenant_id
  ON public.device_sync_logs
  FOR EACH ROW
  EXECUTE FUNCTION public.device_sync_logs_set_tenant_id();

ALTER TABLE public.device_sync_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view sync logs" ON public.device_sync_logs;
CREATE POLICY "Admins can view sync logs"
  ON public.device_sync_logs FOR SELECT
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

DROP POLICY IF EXISTS "Admins can insert sync logs" ON public.device_sync_logs;
CREATE POLICY "Admins can insert sync logs"
  ON public.device_sync_logs FOR INSERT
  WITH CHECK (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

-- ============================================================================
-- END MIGRATION: 20260327123000_device_sync_logs_tenant_scope.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260327124500_app_users_email_lookup_index.sql
-- ============================================================================
-- Speed up email availability checks during signup.
-- Query pattern: select ... from app_users where lower(email)=lower(:email) limit 1

CREATE INDEX IF NOT EXISTS idx_app_users_email_lower
  ON public.app_users ((lower(email)));

-- Also keep a direct index for exact comparisons if callers already normalize.
CREATE INDEX IF NOT EXISTS idx_app_users_email
  ON public.app_users (email);

-- ============================================================================
-- END MIGRATION: 20260327124500_app_users_email_lookup_index.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260328140000_auth_audit_insert_rls_fix.sql
-- ============================================================================
-- Fix 403 on client INSERT into auth_audit after tenant-scoped RLS.
-- Causes:
-- 1) WITH CHECK used "tenant_id = current_tenant_id()" â€” NULL = NULL is not TRUE in SQL.
-- 2) current_tenant_id() prefers JWT tenant_id; if claim is missing/stale vs app_users, CHECK fails.
-- 3) Trigger only set tenant_id when NULL â€” client could pass a wrong tenant_id.

CREATE OR REPLACE FUNCTION public.auth_audit_set_tenant_id()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
SET row_security = off
AS $$
BEGIN
  IF NEW.user_id IS NOT NULL THEN
    SELECT au.tenant_id
      INTO NEW.tenant_id
    FROM public.app_users au
    WHERE au.user_id = NEW.user_id
    LIMIT 1;
  END IF;
  RETURN NEW;
END;
$$;

DROP POLICY IF EXISTS "Users can insert their own auth audit" ON public.auth_audit;
CREATE POLICY "Users can insert their own auth audit"
ON public.auth_audit
FOR INSERT
WITH CHECK (
  auth.uid() = user_id
  AND tenant_id IS NOT DISTINCT FROM (
    SELECT au.tenant_id
    FROM public.app_users au
    WHERE au.user_id = auth.uid()
    LIMIT 1
  )
);

-- ============================================================================
-- END MIGRATION: 20260328140000_auth_audit_insert_rls_fix.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260330120000_admin_dashboard_realtime_tables.sql
-- ============================================================================
-- Enable Supabase Realtime for admin dashboard analytics tables.
-- This ensures card values update automatically (no manual refresh).
DO $$
BEGIN
  -- Models allocated to users.
  IF NOT EXISTS (
    SELECT 1
    FROM pg_publication_rel pr
    JOIN pg_class c ON c.oid = pr.prrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_publication p ON p.oid = pr.prpubid
    WHERE p.pubname = 'supabase_realtime'
      AND n.nspname = 'public'
      AND c.relname = 'activated_models'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.activated_models;
  END IF;

  -- License expiring soon.
  IF NOT EXISTS (
    SELECT 1
    FROM pg_publication_rel pr
    JOIN pg_class c ON c.oid = pr.prrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_publication p ON p.oid = pr.prpubid
    WHERE p.pubname = 'supabase_realtime'
      AND n.nspname = 'public'
      AND c.relname = 'device_licenses'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.device_licenses;
  END IF;

  -- Usage today / yesterday.
  IF NOT EXISTS (
    SELECT 1
    FROM pg_publication_rel pr
    JOIN pg_class c ON c.oid = pr.prrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_publication p ON p.oid = pr.prpubid
    WHERE p.pubname = 'supabase_realtime'
      AND n.nspname = 'public'
      AND c.relname = 'chat_messages'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.chat_messages;
  END IF;
END $$;


-- ============================================================================
-- END MIGRATION: 20260330120000_admin_dashboard_realtime_tables.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260331120000_acord_extract_jobs.sql
-- ============================================================================
-- Persist async ACORD extract job status across process restarts/instances.

CREATE TABLE IF NOT EXISTS public.acord_extract_jobs (
  job_id UUID PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed')),
  error TEXT,
  result JSONB
);

-- Self-heal environments where this table already exists with partial columns.
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS job_id UUID;
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS user_id UUID;
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS status TEXT;
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS error TEXT;
ALTER TABLE public.acord_extract_jobs ADD COLUMN IF NOT EXISTS result JSONB;

-- Best-effort hardening for pre-existing tables.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'acord_extract_jobs_pkey'
      AND conrelid = 'public.acord_extract_jobs'::regclass
  ) THEN
    ALTER TABLE public.acord_extract_jobs ADD PRIMARY KEY (job_id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'acord_extract_jobs_user_id_fkey'
      AND conrelid = 'public.acord_extract_jobs'::regclass
  ) THEN
    ALTER TABLE public.acord_extract_jobs
      ADD CONSTRAINT acord_extract_jobs_user_id_fkey
      FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
  END IF;
END $$;

ALTER TABLE public.acord_extract_jobs
  ALTER COLUMN status SET DEFAULT 'queued';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'acord_extract_jobs_status_check'
      AND conrelid = 'public.acord_extract_jobs'::regclass
  ) THEN
    ALTER TABLE public.acord_extract_jobs
      ADD CONSTRAINT acord_extract_jobs_status_check
      CHECK (status IN ('queued','running','succeeded','failed'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_acord_extract_jobs_user_id ON public.acord_extract_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_acord_extract_jobs_status ON public.acord_extract_jobs(status);
CREATE INDEX IF NOT EXISTS idx_acord_extract_jobs_created_at ON public.acord_extract_jobs(created_at DESC);

DROP TRIGGER IF EXISTS update_acord_extract_jobs_updated_at ON public.acord_extract_jobs;
CREATE TRIGGER update_acord_extract_jobs_updated_at
  BEFORE UPDATE ON public.acord_extract_jobs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.acord_extract_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own acord extract jobs" ON public.acord_extract_jobs;
CREATE POLICY "Users can view own acord extract jobs"
  ON public.acord_extract_jobs
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own acord extract jobs" ON public.acord_extract_jobs;
CREATE POLICY "Users can insert own acord extract jobs"
  ON public.acord_extract_jobs
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own acord extract jobs" ON public.acord_extract_jobs;
CREATE POLICY "Users can update own acord extract jobs"
  ON public.acord_extract_jobs
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Admins can manage acord extract jobs" ON public.acord_extract_jobs;
CREATE POLICY "Admins can manage acord extract jobs"
  ON public.acord_extract_jobs
  FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));


-- ============================================================================
-- END MIGRATION: 20260331120000_acord_extract_jobs.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260331133000_acord_extract_jobs_user_id_normalization.sql
-- ============================================================================
-- Normalize legacy acord_extract_jobs schemas to user_id-based ownership.
-- Safe to run multiple times.

ALTER TABLE public.acord_extract_jobs
  ADD COLUMN IF NOT EXISTS user_id UUID;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'acord_extract_jobs'
      AND column_name = 'created_by'
  ) THEN
    EXECUTE '
      UPDATE public.acord_extract_jobs
      SET user_id = created_by
      WHERE user_id IS NULL
    ';
  END IF;
END $$;

-- Remove rows that cannot be attributed to any user; they break ownership policies.
DELETE FROM public.acord_extract_jobs
WHERE user_id IS NULL;

ALTER TABLE public.acord_extract_jobs
  ALTER COLUMN user_id SET NOT NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'acord_extract_jobs_created_by_fkey'
      AND conrelid = 'public.acord_extract_jobs'::regclass
  ) THEN
    ALTER TABLE public.acord_extract_jobs
      DROP CONSTRAINT acord_extract_jobs_created_by_fkey;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'acord_extract_jobs_user_id_fkey'
      AND conrelid = 'public.acord_extract_jobs'::regclass
  ) THEN
    ALTER TABLE public.acord_extract_jobs
      ADD CONSTRAINT acord_extract_jobs_user_id_fkey
      FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_acord_extract_jobs_user_id
  ON public.acord_extract_jobs(user_id);


-- ============================================================================
-- END MIGRATION: 20260331133000_acord_extract_jobs_user_id_normalization.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260331143000_acord_extract_jobs_phase.sql
-- ============================================================================
-- Add phase marker so status polling can show extraction progress details.

ALTER TABLE public.acord_extract_jobs
  ADD COLUMN IF NOT EXISTS phase TEXT;

UPDATE public.acord_extract_jobs
SET phase = COALESCE(
  phase,
  CASE
    WHEN status = 'queued' THEN 'queued'
    WHEN status = 'running' THEN 'generate_extracting'
    WHEN status = 'succeeded' THEN 'completed'
    WHEN status = 'failed' THEN 'failed'
    ELSE NULL
  END
);


-- ============================================================================
-- END MIGRATION: 20260331143000_acord_extract_jobs_phase.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260408000000_model_registry.sql
-- ============================================================================
-- Model Registry: stores benchmark metrics per insurance task/model.
-- This table is read via backend admin endpoints (service role) and optionally
-- populated via MLflow sync.

create table if not exists public.model_registry (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid null,

  task_key text not null,
  task_label text not null,

  base_model text not null,
  display_name text null,

  bleu_score double precision null,
  f1_score double precision null,
  latency_ms double precision null,

  is_best_for_task boolean not null default false,

  mlflow_run_id text null,
  mlflow_experiment_id text null,
  source text not null default 'manual',

  metadata jsonb null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Common query patterns
create index if not exists model_registry_task_key_idx on public.model_registry (task_key);
create index if not exists model_registry_tenant_id_idx on public.model_registry (tenant_id);
create index if not exists model_registry_best_idx on public.model_registry (task_key, is_best_for_task);

-- MLflow sync uses run_id to upsert
create unique index if not exists model_registry_mlflow_run_id_uidx
  on public.model_registry (mlflow_run_id)
  where mlflow_run_id is not null;

-- Keep updated_at fresh on updates
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_model_registry_updated_at on public.model_registry;
create trigger set_model_registry_updated_at
before update on public.model_registry
for each row
execute function public.set_updated_at();


-- ============================================================================
-- END MIGRATION: 20260408000000_model_registry.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260408070000_merge_tenant_agent_packs_on_signup.sql
-- ============================================================================
-- ============================================================================
-- Migration: 20260408070000_merge_tenant_agent_packs_on_signup.sql
--
-- Signup hardening:
-- When a user signs up into an existing tenant, their chosen "agent_packs" must
-- never overwrite what the global admin already selected for the tenant.
--
-- Rule:
--   - For new tenant creation: tenant.agent_packs = requested_agent_packs
--   - For existing tenant: tenant.agent_packs = DISTINCT(tenant.agent_packs âˆª requested_agent_packs)
--   - Never remove packs via signup.
--
-- The tenant-level limit enforcement trigger (trg_enforce_tenant_agent_pack_limit)
-- remains the source of truth for max_agent_packs.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.handle_new_app_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  default_tenant_id          UUID;
  resolved_tenant_id         UUID;
  requested_tenant_name      TEXT;
  requested_plan             TEXT;
  requested_role             TEXT;
  requested_signup_version   TEXT;
  requested_device_name      TEXT;
  requested_device_profile   JSONB;
  requested_agent_packs      TEXT[];
  requested_addon_slots      INTEGER;
  resolved_slots_total       INTEGER;
  resolved_max_packs         INTEGER;
  resolved_max_models        INTEGER;
  normalized_slug            TEXT;
  generated_slug             TEXT;
BEGIN
  requested_tenant_name    := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'tenant_name',           '')), '');
  requested_plan           := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'plan',                  '')), '');
  requested_role           := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'requested_role',        '')), '');
  requested_signup_version := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'signup_wizard_version', '')), '');
  requested_device_name    := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'device_name',           '')), '');
  requested_device_profile := COALESCE(NEW.raw_user_meta_data -> 'device_profile', '{}'::jsonb);

  SELECT ARRAY(
    SELECT jsonb_array_elements_text(
      COALESCE(NEW.raw_user_meta_data -> 'agent_packs', '[]'::jsonb)
    )
  ) INTO requested_agent_packs;

  requested_agent_packs := COALESCE(requested_agent_packs, '{}'::text[]);

  requested_addon_slots := GREATEST(0, LEAST(5,
    COALESCE((NEW.raw_user_meta_data ->> 'workflow_addon_slots')::INTEGER, 0)
  ));

  IF requested_device_name IS NULL THEN
    requested_device_name := NULLIF(trim(COALESCE(requested_device_profile ->> 'device_name', '')), '');
  END IF;

  resolved_max_packs := COALESCE(
    (NEW.raw_user_meta_data ->> 'max_agent_packs')::INTEGER,
    (SELECT max_agent_packs FROM public.plan_limits(COALESCE(requested_plan, 'starter')))
  );
  resolved_max_models := COALESCE(
    (NEW.raw_user_meta_data ->> 'max_active_models')::INTEGER,
    (SELECT max_active_models FROM public.plan_limits(COALESCE(requested_plan, 'starter')))
  );
  resolved_slots_total := CASE
    WHEN requested_plan = 'enterprise'   THEN NULL
    WHEN requested_plan = 'professional' THEN 15 + requested_addon_slots
    ELSE                                      3  + requested_addon_slots
  END;

  SELECT id INTO default_tenant_id
  FROM public.tenants WHERE slug = 'default-tenant' LIMIT 1;
  resolved_tenant_id := default_tenant_id;

  IF requested_tenant_name IS NOT NULL THEN
    SELECT id INTO resolved_tenant_id
    FROM public.tenants
    WHERE is_active = true
      AND lower(trim(name)) = lower(trim(requested_tenant_name))
    ORDER BY created_at ASC, id ASC
    LIMIT 1;

    IF resolved_tenant_id IS NULL THEN
      normalized_slug := lower(regexp_replace(requested_tenant_name, '[^a-zA-Z0-9]+', '-', 'g'));
      normalized_slug := trim(both '-' FROM normalized_slug);
      IF normalized_slug = '' THEN normalized_slug := 'tenant'; END IF;
      generated_slug := normalized_slug || '-' || substring(replace(NEW.id::text, '-', ''), 1, 8);

      INSERT INTO public.tenants (
        slug, name, is_active,
        plan, tier,
        agent_packs, workflow_addon_slots, workflow_slots_total,
        max_agent_packs, max_active_models,
        metadata
      )
      VALUES (
        generated_slug,
        requested_tenant_name,
        true,
        COALESCE(requested_plan, 'starter'),
        COALESCE(requested_plan, 'starter'),
        requested_agent_packs,
        requested_addon_slots,
        resolved_slots_total,
        resolved_max_packs,
        resolved_max_models,
        jsonb_strip_nulls(jsonb_build_object(
          'created_from_signup', true,
          'signup_user_id',      NEW.id,
          'plan',                requested_plan
        ))
      )
      ON CONFLICT (slug) DO UPDATE SET
        name                 = EXCLUDED.name,
        plan                 = EXCLUDED.plan,
        tier                 = EXCLUDED.tier,
        agent_packs          = EXCLUDED.agent_packs,
        workflow_addon_slots = EXCLUDED.workflow_addon_slots,
        workflow_slots_total = EXCLUDED.workflow_slots_total,
        max_agent_packs      = EXCLUDED.max_agent_packs,
        max_active_models    = EXCLUDED.max_active_models,
        metadata             = COALESCE(public.tenants.metadata, '{}'::jsonb) || EXCLUDED.metadata
      RETURNING id INTO resolved_tenant_id;
    ELSE
      -- Existing tenant: only ADD packs, never overwrite/remove.
      UPDATE public.tenants SET
        agent_packs = (
          SELECT ARRAY(
            SELECT DISTINCT p
            FROM unnest(COALESCE(agent_packs, '{}'::text[]) || requested_agent_packs) AS p
          )
        ),
        -- Do not let signup change plan/tier/limits; keep admin-selected values.
        workflow_addon_slots = workflow_addon_slots,
        workflow_slots_total = workflow_slots_total,
        max_agent_packs      = max_agent_packs,
        max_active_models    = max_active_models
      WHERE id = resolved_tenant_id;
    END IF;
  END IF;

  INSERT INTO public.app_users (user_id, email, full_name, tenant_id, status, metadata)
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    NULLIF(NEW.raw_user_meta_data ->> 'full_name', ''),
    resolved_tenant_id,
    'active',
    jsonb_strip_nulls(jsonb_build_object(
      'onboarding_plan',                  requested_plan,
      'onboarding_agent_packs',           to_jsonb(requested_agent_packs),
      'onboarding_workflow_addon_slots',  requested_addon_slots,
      'onboarding_workflow_slots_total',  resolved_slots_total,
      'onboarding_requested_role',        requested_role,
      'onboarding_signup_wizard_version', requested_signup_version,
      'onboarding_device_name',           requested_device_name,
      'onboarding_tenant_name',           requested_tenant_name,
      'onboarding_device_profile',        requested_device_profile
    ))
  )
  ON CONFLICT (user_id) DO UPDATE
  SET
    email      = EXCLUDED.email,
    full_name  = COALESCE(EXCLUDED.full_name, public.app_users.full_name),
    tenant_id  = COALESCE(EXCLUDED.tenant_id, public.app_users.tenant_id),
    metadata   = COALESCE(public.app_users.metadata, '{}'::jsonb) || EXCLUDED.metadata;

  IF requested_device_name IS NOT NULL THEN
    INSERT INTO public.devices (
      device_name, device_token, registered_by, tenant_id, status,
      os_type, app_version, metadata
    )
    VALUES (
      requested_device_name,
      public.generate_device_token(),
      NEW.id,
      resolved_tenant_id,
      'never_checked_in',
      NULLIF(requested_device_profile ->> 'os_name',    ''),
      NULLIF(requested_device_profile ->> 'app_version',''),
      jsonb_strip_nulls(jsonb_build_object(
        'created_from_signup', true,
        'signup_user_id',      NEW.id,
        'device_profile',      requested_device_profile
      ))
    )
    ON CONFLICT DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  RAISE NOTICE 'âœ“ merge_tenant_agent_packs_on_signup migration complete.';
END;
$$;


-- ============================================================================
-- END MIGRATION: 20260408070000_merge_tenant_agent_packs_on_signup.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260408090000_tenant_signup_config_exact_lookup_rpc.sql
-- ============================================================================
-- ============================================================================
-- Migration: 20260408090000_tenant_signup_config_exact_lookup_rpc.sql
--
-- Production hardening: deterministic tenant lookup for signup wizard.
--
-- The Signup wizard must resolve the tenant deterministically using the same
-- normalization strategy as the DB trigger:
--   lower(trim(tenants.name)) = lower(trim(requested_tenant_name))
--
-- Exposes a JSONB payload for:
--   - tenant plan lock
--   - agent pack preselection + remaining pack slots
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_tenant_signup_config_exact(p_tenant_name TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_normalized_name TEXT := lower(trim(p_tenant_name));
  v_tenants_rec RECORD;
  v_packs TEXT[];
  v_max_packs INTEGER;
  v_remaining INTEGER;
BEGIN
  IF v_normalized_name IS NULL OR v_normalized_name = '' THEN
    RETURN NULL;
  END IF;

  SELECT
    id,
    slug,
    name,
    plan,
    max_agent_packs,
    COALESCE(agent_packs, '{}'::text[]) AS agent_packs,
    COALESCE(workflow_addon_slots, 0) AS workflow_addon_slots,
    workflow_slots_total
  INTO v_tenants_rec
  FROM public.tenants
  WHERE is_active = true
    AND lower(trim(name)) = v_normalized_name
  ORDER BY created_at ASC, id ASC
  LIMIT 1;

  IF v_tenants_rec.id IS NULL THEN
    RETURN NULL;
  END IF;

  v_packs := v_tenants_rec.agent_packs;
  v_max_packs := v_tenants_rec.max_agent_packs;

  IF v_max_packs IS NULL THEN
    v_remaining := NULL; -- unlimited
  ELSE
    v_remaining := GREATEST(0, v_max_packs - COALESCE(cardinality(v_packs), 0));
  END IF;

  RETURN jsonb_build_object(
    'tenant', jsonb_build_object(
      'id', v_tenants_rec.id,
      'slug', v_tenants_rec.slug,
      'name', v_tenants_rec.name
    ),
    'plan', COALESCE(v_tenants_rec.plan, 'starter'),
    'agent_packs', v_packs,
    'max_agent_packs', v_max_packs,
    'remaining_pack_slots', v_remaining,
    'workflow_addon_slots', v_tenants_rec.workflow_addon_slots,
    'workflow_slots_total', v_tenants_rec.workflow_slots_total
  );
END;
$$;


-- ============================================================================
-- END MIGRATION: 20260408090000_tenant_signup_config_exact_lookup_rpc.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260409090000_tenants_agent_packs_columns.sql
-- ============================================================================
-- Backward-compatible tenants columns required by signup wizard + trigger.
-- Fixes: column "agent_packs" does not exist (42703)

ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS agent_packs TEXT[] NOT NULL DEFAULT '{}'::text[],
  ADD COLUMN IF NOT EXISTS workflow_addon_slots INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS workflow_slots_total INTEGER,
  ADD COLUMN IF NOT EXISTS max_agent_packs INTEGER,
  ADD COLUMN IF NOT EXISTS max_active_models INTEGER;

-- Ensure legacy rows have sane defaults even if columns existed but were nullable.
UPDATE public.tenants
SET
  agent_packs = COALESCE(agent_packs, '{}'::text[]),
  workflow_addon_slots = COALESCE(workflow_addon_slots, 0)
WHERE agent_packs IS NULL
   OR workflow_addon_slots IS NULL;


-- ============================================================================
-- END MIGRATION: 20260409090000_tenants_agent_packs_columns.sql
-- ============================================================================

-- ============================================================================
-- BEGIN MIGRATION: 20260409090500_plan_limits_rpc.sql
-- ============================================================================
-- Plan limit lookup used by signup trigger (handle_new_app_user).
-- Keeps plan constraints in the database to avoid runtime failures.

CREATE OR REPLACE FUNCTION public.plan_limits(p_plan TEXT)
RETURNS TABLE (
  max_agent_packs INTEGER,
  max_active_models INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_plan TEXT := lower(trim(COALESCE(p_plan, 'starter')));
BEGIN
  IF v_plan = 'professional' THEN
    max_agent_packs := 3;
    max_active_models := 8;
  ELSIF v_plan = 'enterprise' THEN
    max_agent_packs := NULL; -- unlimited
    max_active_models := NULL; -- unlimited
  ELSE
    -- starter (default)
    max_agent_packs := 1;
    max_active_models := 3;
  END IF;

  RETURN NEXT;
END;
$$;


-- ============================================================================
-- END MIGRATION: 20260409090500_plan_limits_rpc.sql
-- ============================================================================

