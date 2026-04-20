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

-- Required: supabase_auth_admin must be able to call the hook.
GRANT EXECUTE ON FUNCTION public.custom_access_token_hook TO supabase_auth_admin;

-- Prevent regular users from calling it directly.
REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook FROM authenticated, anon, public;
