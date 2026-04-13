-- Plan limit lookup used by signup trigger (handle_new_app_user).
-- Keeps plan constraints in the database to avoid runtime failures.

CREATE OR REPLACE FUNCTION public.plan_limits(p_plan TEXT)
RETURNS TABLE (
  max_agent_packs INTEGER,
  max_active_models INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_plan TEXT := lower(trim(COALESCE(p_plan, 'starter')));
BEGIN
  IF v_plan = 'professional' THEN
    max_agent_packs := 3;
    max_active_models := 8;
  ELSIF v_plan = 'enterprise' THEN
    max_agent_packs := NULL; -- unlimited
    max_active_models := NULL; -- unlimited
  ELSE
    -- starter (default)
    max_agent_packs := 1;
    max_active_models := 3;
  END IF;

  RETURN NEXT;
END;
$$;

