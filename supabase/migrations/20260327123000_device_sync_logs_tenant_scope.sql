-- Tenant-scope device sync logs for notification isolation.

ALTER TABLE public.device_sync_logs
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL;

-- Backfill from owning device.
UPDATE public.device_sync_logs dsl
SET tenant_id = d.tenant_id
FROM public.devices d
WHERE dsl.tenant_id IS NULL
  AND dsl.device_id = d.id;

CREATE INDEX IF NOT EXISTS idx_device_sync_logs_tenant_created
  ON public.device_sync_logs (tenant_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.device_sync_logs_set_tenant_id()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.tenant_id IS NULL AND NEW.device_id IS NOT NULL THEN
    SELECT d.tenant_id
      INTO NEW.tenant_id
    FROM public.devices d
    WHERE d.id = NEW.device_id
    LIMIT 1;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_device_sync_logs_set_tenant_id ON public.device_sync_logs;
CREATE TRIGGER trg_device_sync_logs_set_tenant_id
  BEFORE INSERT OR UPDATE OF device_id, tenant_id
  ON public.device_sync_logs
  FOR EACH ROW
  EXECUTE FUNCTION public.device_sync_logs_set_tenant_id();

ALTER TABLE public.device_sync_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view sync logs" ON public.device_sync_logs;
CREATE POLICY "Admins can view sync logs"
  ON public.device_sync_logs FOR SELECT
  USING (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );

DROP POLICY IF EXISTS "Admins can insert sync logs" ON public.device_sync_logs;
CREATE POLICY "Admins can insert sync logs"
  ON public.device_sync_logs FOR INSERT
  WITH CHECK (
    (
      public.has_role(auth.uid(), 'admin'::public.app_role)
      OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
    )
    AND tenant_id = public.current_tenant_id()
  );
