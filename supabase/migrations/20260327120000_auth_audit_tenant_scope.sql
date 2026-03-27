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
