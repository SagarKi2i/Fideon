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
