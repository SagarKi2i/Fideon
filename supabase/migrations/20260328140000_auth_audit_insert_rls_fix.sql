-- Fix 403 on client INSERT into auth_audit after tenant-scoped RLS.
-- Causes:
-- 1) WITH CHECK used "tenant_id = current_tenant_id()" — NULL = NULL is not TRUE in SQL.
-- 2) current_tenant_id() prefers JWT tenant_id; if claim is missing/stale vs app_users, CHECK fails.
-- 3) Trigger only set tenant_id when NULL — client could pass a wrong tenant_id.

CREATE OR REPLACE FUNCTION public.auth_audit_set_tenant_id()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
SET row_security = off
AS $$
BEGIN
  IF NEW.user_id IS NOT NULL THEN
    SELECT au.tenant_id
      INTO NEW.tenant_id
    FROM public.app_users au
    WHERE au.user_id = NEW.user_id
    LIMIT 1;
  END IF;
  RETURN NEW;
END;
$$;

DROP POLICY IF EXISTS "Users can insert their own auth audit" ON public.auth_audit;
CREATE POLICY "Users can insert their own auth audit"
ON public.auth_audit
FOR INSERT
WITH CHECK (
  auth.uid() = user_id
  AND tenant_id IS NOT DISTINCT FROM (
    SELECT au.tenant_id
    FROM public.app_users au
    WHERE au.user_id = auth.uid()
    LIMIT 1
  )
);
