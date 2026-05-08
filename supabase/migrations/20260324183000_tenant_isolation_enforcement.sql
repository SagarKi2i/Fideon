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
