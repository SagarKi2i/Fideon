-- Fix infinite recursion (42P17) in app_users, devices, tenants, and user_roles RLS policies.
-- Root cause: 20260317100000_tenant_scope_rls_hardening.sql introduced policies on app_users
-- that do EXISTS (SELECT 1 FROM public.app_users me ...) — a self-referential subquery that
-- triggers the same RLS policy, causing infinite recursion.
--
-- Fix: replace all tenant-JOIN policies with simple has_role() checks.
-- Devices and tenants also referenced app_users inside their policies, causing the same 500.

-- ── app_users ─────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "Admins can view app users in own tenant"    ON public.app_users;
DROP POLICY IF EXISTS "Admins can manage app users in own tenant"  ON public.app_users;
DROP POLICY IF EXISTS "Global admins can manage all app users"     ON public.app_users;

-- Self-view: every authenticated user can see their own row
DROP POLICY IF EXISTS "Users can view own app user record"         ON public.app_users;
CREATE POLICY "Users can view own app user record"
  ON public.app_users FOR SELECT
  USING (auth.uid() = user_id);

-- Admins can view all app users (no self-referential JOIN)
CREATE POLICY "Admins can view all app users"
  ON public.app_users FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'::public.app_role));

-- Global admins can do everything
CREATE POLICY "Global admins can manage all app users"
  ON public.app_users FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- ── tenants ───────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "Admins can manage own tenant"         ON public.tenants;
DROP POLICY IF EXISTS "Global admins can manage all tenants" ON public.tenants;

CREATE POLICY "Admins can view all tenants"
  ON public.tenants FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'::public.app_role));

CREATE POLICY "Global admins can manage all tenants"
  ON public.tenants FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- ── user_roles ────────────────────────────────────────────────────────────────
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

CREATE POLICY "Admins can manage all user roles"
  ON public.user_roles FOR ALL
  USING (public.has_role(auth.uid(), 'admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

CREATE POLICY "Global admins can manage all user roles"
  ON public.user_roles FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));

-- ── devices ───────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "Admins can view devices in own tenant"    ON public.devices;
DROP POLICY IF EXISTS "Admins can insert devices in own tenant"  ON public.devices;
DROP POLICY IF EXISTS "Admins can update devices in own tenant"  ON public.devices;
DROP POLICY IF EXISTS "Admins can delete devices in own tenant"  ON public.devices;
DROP POLICY IF EXISTS "Global admins can manage all devices"     ON public.devices;

CREATE POLICY "Admins can view all devices"
  ON public.devices FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'::public.app_role));

CREATE POLICY "Admins can manage all devices"
  ON public.devices FOR ALL
  USING (public.has_role(auth.uid(), 'admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

CREATE POLICY "Global admins can manage all devices"
  ON public.devices FOR ALL
  USING (public.has_role(auth.uid(), 'global_admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'global_admin'::public.app_role));
