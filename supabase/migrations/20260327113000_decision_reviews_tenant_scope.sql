-- Enforce tenant-scoped isolation for decision_reviews.

ALTER TABLE public.decision_reviews
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL;

-- Backfill tenant ownership from requester profile.
UPDATE public.decision_reviews dr
SET tenant_id = au.tenant_id
FROM public.app_users au
WHERE dr.tenant_id IS NULL
  AND dr.user_id = au.user_id;

CREATE INDEX IF NOT EXISTS idx_decision_reviews_tenant_status_created
  ON public.decision_reviews (tenant_id, status, created_at DESC);

ALTER TABLE public.decision_reviews ENABLE ROW LEVEL SECURITY;

-- Replace legacy broad policies with tenant-scoped policies.
DROP POLICY IF EXISTS "Users can view their own reviews" ON public.decision_reviews;
DROP POLICY IF EXISTS "Users can create reviews" ON public.decision_reviews;
DROP POLICY IF EXISTS "Admins can view all reviews" ON public.decision_reviews;
DROP POLICY IF EXISTS "Admins can update reviews" ON public.decision_reviews;
DROP POLICY IF EXISTS "Users can update own pending reviews" ON public.decision_reviews;

CREATE POLICY "Users can view their own reviews"
ON public.decision_reviews FOR SELECT
USING (
  auth.uid() = user_id
  AND tenant_id = public.current_tenant_id()
);

CREATE POLICY "Users can create reviews"
ON public.decision_reviews FOR INSERT
WITH CHECK (
  auth.uid() = user_id
  AND tenant_id = public.current_tenant_id()
);

CREATE POLICY "Admins can view tenant reviews"
ON public.decision_reviews FOR SELECT
USING (
  (
    public.has_role(auth.uid(), 'admin'::public.app_role)
    OR public.has_role(auth.uid(), 'global_admin'::public.app_role)
  )
  AND tenant_id = public.current_tenant_id()
);

CREATE POLICY "Admins can update tenant reviews"
ON public.decision_reviews FOR UPDATE
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
