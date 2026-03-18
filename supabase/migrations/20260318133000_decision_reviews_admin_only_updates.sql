-- Enforce admin/global_admin-only approval/rejection on decision review requests.
-- This removes end-user status updates so only privileged reviewers can decide.

ALTER TABLE public.decision_reviews ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can update own pending reviews" ON public.decision_reviews;

DROP POLICY IF EXISTS "Admins can update reviews" ON public.decision_reviews;
CREATE POLICY "Admins can update reviews"
ON public.decision_reviews FOR UPDATE
USING (public.has_role(auth.uid(), 'admin'::public.app_role))
WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));
