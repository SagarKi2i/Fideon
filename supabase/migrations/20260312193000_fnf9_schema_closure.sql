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
