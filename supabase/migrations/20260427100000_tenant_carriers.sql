-- Custom carriers added by a tenant's admin/global_admin.
-- Fixed carriers (Travelers, Chubb, etc.) live in frontend static metadata.
-- This table stores ONLY tenant-specific extras — fully isolated per tenant via RLS.
-- When a custom carrier is deleted, its credentials are removed by the backend before this row is deleted.

CREATE TABLE IF NOT EXISTS public.tenant_carriers (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  carrier_id  TEXT        NOT NULL,
  name        TEXT        NOT NULL CHECK (length(trim(name)) > 0),
  logo        TEXT        NOT NULL DEFAULT '🏢',
  created_by  UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, carrier_id)
);

CREATE INDEX IF NOT EXISTS idx_tenant_carriers_tenant
  ON public.tenant_carriers (tenant_id);

ALTER TABLE public.tenant_carriers ENABLE ROW LEVEL SECURITY;

-- Admin and global_admin within the same tenant have full access.
-- No policy for user/viewer/guest — table is invisible to them.
CREATE POLICY "admins_manage_tenant_carriers"
  ON public.tenant_carriers
  FOR ALL
  USING (
    (
      public.has_role(auth.uid(), 'global_admin'::public.app_role)
      OR public.has_role(auth.uid(), 'admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  )
  WITH CHECK (
    (
      public.has_role(auth.uid(), 'global_admin'::public.app_role)
      OR public.has_role(auth.uid(), 'admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );