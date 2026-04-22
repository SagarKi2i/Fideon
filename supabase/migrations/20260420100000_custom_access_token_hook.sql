-- =============================================================================
-- Custom Access Token Hook
-- Embeds the user's app_role into every JWT issued by Supabase Auth.
--
-- After this hook is deployed AND registered in the Supabase dashboard
-- (Authentication → Hooks → Custom Access Token), every JWT will contain:
--   app_metadata.role = "global_admin" | "admin" | "user" | "viewer" | "guest"
--
-- The frontend reads this claim instantly from the token (zero HTTP calls).
-- The HTTP fallback in useUserRole is kept for tokens issued before the hook.
--
-- AFTER running this migration:
--   1. Go to Supabase Dashboard → Authentication → Hooks
--   2. Enable "Custom Access Token" hook
--   3. Select function: public.custom_access_token_hook
-- =============================================================================

CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  claims   jsonb;
  user_role text;
BEGIN
  -- Look up the user's role in the user_roles table.
  SELECT role::text INTO user_role
  FROM public.user_roles
  WHERE user_id = (event->>'user_id')::uuid;

  -- Embed role into app_metadata (falls back to 'user' if no row found).
  claims := event->'claims';
  claims := jsonb_set(
    claims,
    '{app_metadata}',
    COALESCE(claims->'app_metadata', '{}'::jsonb)
      || jsonb_build_object('role', COALESCE(user_role, 'user'))
  );

  RETURN jsonb_set(event, '{claims}', claims);
END;
$$;

-- Required: supabase_auth_admin must be able to reach the public schema and call the hook.
-- GoTrue connects as supabase_auth_admin (not postgres). In self-hosted Supabase, postgres is
-- NOT a superuser — supabase_admin owns the public schema and must issue schema-level grants.
SET ROLE supabase_admin;
GRANT USAGE ON SCHEMA public TO supabase_auth_admin;
RESET ROLE;

GRANT EXECUTE ON FUNCTION public.custom_access_token_hook TO supabase_auth_admin;

-- The hook body reads user_roles to embed the role claim.
-- Grant SELECT so the lookup succeeds even when the function owner is not a superuser
-- (e.g. self-hosted Supabase where postgres != superuser, or when RLS is active).
GRANT SELECT ON public.user_roles TO supabase_auth_admin;

-- Prevent regular users from calling it directly.
REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook FROM authenticated, anon, public;
