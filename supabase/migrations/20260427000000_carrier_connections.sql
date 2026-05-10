-- Carrier connections: stores per-tenant carrier portal credentials (password is Fernet-encrypted).
-- Only admin / global_admin roles can read or write via RLS.
-- Regular users (user/viewer/guest) have zero access — the table is invisible to them.
-- The backend decrypts passwords in memory when making carrier API calls on behalf of any tenant user.

CREATE TABLE IF NOT EXISTS public.carrier_connections (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  carrier_id          TEXT        NOT NULL,
  username            TEXT        NOT NULL,
  encrypted_password  TEXT        NOT NULL,
  enterprise_id       TEXT,
  connected_by        UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
  connected_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_synced_at      TIMESTAMPTZ,
  status              TEXT        NOT NULL DEFAULT 'active'
                                  CHECK (status IN ('active', 'inactive')),
  UNIQUE (tenant_id, carrier_id)
);

CREATE INDEX IF NOT EXISTS idx_carrier_connections_tenant
  ON public.carrier_connections (tenant_id, carrier_id);

ALTER TABLE public.carrier_connections ENABLE ROW LEVEL SECURITY;

-- Admin and global_admin in the same tenant have full access.
-- No policy is created for user/viewer/guest, so those roles cannot query this table at all.
CREATE POLICY "admins_manage_carrier_connections"
  ON public.carrier_connections
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