-- Tenant-scope pod activation requests for reliable isolation and admin review UX.

ALTER TABLE public.pod_activation_requests
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL;

-- Backfill tenant ownership from requester profile.
UPDATE public.pod_activation_requests par
SET tenant_id = au.tenant_id
FROM public.app_users au
WHERE par.tenant_id IS NULL
  AND par.user_id = au.user_id;

CREATE INDEX IF NOT EXISTS idx_par_tenant_status_requested
  ON public.pod_activation_requests (tenant_id, status, requested_at DESC);

ALTER TABLE public.pod_activation_requests ENABLE ROW LEVEL SECURITY;

-- Requesters can see their own rows in their tenant.
DROP POLICY IF EXISTS "Users can view their own requests" ON public.pod_activation_requests;
CREATE POLICY "Users can view their own requests"
ON public.pod_activation_requests FOR SELECT
USING (
  auth.uid() = user_id
  AND tenant_id = public.current_tenant_id()
);

-- Requesters can create rows only for themselves in their tenant.
DROP POLICY IF EXISTS "Users can create activation requests" ON public.pod_activation_requests;
CREATE POLICY "Users can create activation requests"
ON public.pod_activation_requests FOR INSERT
WITH CHECK (
  auth.uid() = user_id
  AND tenant_id = public.current_tenant_id()
);

-- Tenant admins/global_admin can view tenant queue.
DROP POLICY IF EXISTS "Admins can view all requests" ON public.pod_activation_requests;
CREATE POLICY "Admins can view all requests"
ON public.pod_activation_requests FOR SELECT
USING (
  (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
  )
  AND tenant_id = public.current_tenant_id()
);

-- Tenant admins/global_admin can update only tenant rows.
DROP POLICY IF EXISTS "Admins can update requests" ON public.pod_activation_requests;
CREATE POLICY "Admins can update requests"
ON public.pod_activation_requests FOR UPDATE
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

-- Users can cancel only own pending requests in their tenant.
DROP POLICY IF EXISTS "Users can cancel pending requests" ON public.pod_activation_requests;
CREATE POLICY "Users can cancel pending requests"
ON public.pod_activation_requests FOR DELETE
USING (
  auth.uid() = user_id
  AND status = 'pending'
  AND tenant_id = public.current_tenant_id()
);
