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
