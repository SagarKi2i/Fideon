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
