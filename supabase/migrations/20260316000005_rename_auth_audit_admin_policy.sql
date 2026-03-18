-- ============================================================
-- Correction 5: Rename misleading RLS policy on auth_audit
-- Old name: "Admins see user+admin auth audit"
--   → implied only admin+user rows visible, omitted viewer+guest
-- New name: "Admins see all except global_admin auth audit"
--   → accurately describes the condition: role IN (admin, user, viewer, guest)
-- The condition itself is unchanged — only the policy name is corrected.
-- ============================================================

-- Drop old misleadingly-named policy
DROP POLICY IF EXISTS "Admins see user+admin auth audit" ON public.auth_audit;

-- Recreate with accurate name
CREATE POLICY "Admins see all except global_admin auth audit"
ON public.auth_audit
FOR SELECT
USING (
  public.has_role(auth.uid(), 'admin'::public.app_role)
  AND role IN ('admin', 'user', 'viewer', 'guest')
);
