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
