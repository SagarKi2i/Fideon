-- =============================================================================
-- Migration: 20260416100000_seat_limit_enforcement.sql
--
-- Enforces per-plan user seat limits end-to-end:
--   - Adds max_users column to tenants (NULL = unlimited / enterprise)
--   - Backfills max_users from existing plan values
--   - Auto-syncs max_users whenever a tenant's plan changes (INSERT or UPDATE)
--   - Updates plan_limits() RPC to return max_users
--   - Adds a BEFORE INSERT trigger on app_users that raises
--     FIDEON_OS_LIMIT:SEATS when the tenant is at its seat limit
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Add max_users column to tenants
-- ---------------------------------------------------------------------------
ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS max_users INTEGER; -- NULL = unlimited (enterprise)

-- ---------------------------------------------------------------------------
-- 2. Backfill max_users from existing plan column for all current tenants
-- ---------------------------------------------------------------------------
UPDATE public.tenants
SET max_users = CASE
  WHEN lower(trim(COALESCE(plan, 'starter'))) = 'enterprise'    THEN NULL
  WHEN lower(trim(COALESCE(plan, 'starter'))) = 'professional'  THEN 25
  ELSE 5  -- starter, free, or any unrecognised legacy plan
END
WHERE max_users IS NULL;

-- ---------------------------------------------------------------------------
-- 3. Trigger: keep max_users in sync whenever plan is set or changed
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.sync_tenant_max_users()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- On INSERT: always derive max_users from the plan being inserted.
  -- On UPDATE: only recalculate when plan actually changes.
  IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND NEW.plan IS DISTINCT FROM OLD.plan) THEN
    NEW.max_users := CASE
      WHEN lower(trim(COALESCE(NEW.plan, 'starter'))) = 'enterprise'   THEN NULL
      WHEN lower(trim(COALESCE(NEW.plan, 'starter'))) = 'professional' THEN 25
      ELSE 5
    END;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_tenant_max_users ON public.tenants;
CREATE TRIGGER trg_sync_tenant_max_users
  BEFORE INSERT OR UPDATE OF plan ON public.tenants
  FOR EACH ROW
  EXECUTE FUNCTION public.sync_tenant_max_users();

-- ---------------------------------------------------------------------------
-- 4. Update plan_limits() RPC to expose max_users
--    Must DROP first because the return type (OUT columns) is changing.
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.plan_limits(TEXT);

CREATE OR REPLACE FUNCTION public.plan_limits(p_plan TEXT)
RETURNS TABLE (
  max_agent_packs  INTEGER,
  max_active_models INTEGER,
  max_users        INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_plan TEXT := lower(trim(COALESCE(p_plan, 'starter')));
BEGIN
  IF v_plan = 'professional' THEN
    max_agent_packs   := 3;
    max_active_models := 8;
    max_users         := 25;
  ELSIF v_plan = 'enterprise' THEN
    max_agent_packs   := NULL; -- unlimited
    max_active_models := NULL; -- unlimited
    max_users         := NULL; -- unlimited
  ELSE
    -- starter (default for all unrecognised plans)
    max_agent_packs   := 1;
    max_active_models := 3;
    max_users         := 5;
  END IF;

  RETURN NEXT;
END;
$$;

-- ---------------------------------------------------------------------------
-- 5. BEFORE INSERT trigger on app_users: enforce seat limit
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.enforce_tenant_seat_limit()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_max_users     INTEGER;
  v_current_count INTEGER;
BEGIN
  -- No tenant assigned: no limit to enforce.
  IF NEW.tenant_id IS NULL THEN
    RETURN NEW;
  END IF;

  -- If this user_id already exists in app_users this is an upsert / re-assignment,
  -- not a net-new seat — skip the limit check so existing users are never blocked.
  IF EXISTS (
    SELECT 1 FROM public.app_users WHERE user_id = NEW.user_id
  ) THEN
    RETURN NEW;
  END IF;

  -- Look up the tenant's seat limit (NULL = unlimited).
  SELECT t.max_users
    INTO v_max_users
    FROM public.tenants t
   WHERE t.id = NEW.tenant_id
   LIMIT 1;

  IF v_max_users IS NULL THEN
    RETURN NEW;
  END IF;

  -- Count active seats already consumed by this tenant.
  SELECT COUNT(*)
    INTO v_current_count
    FROM public.app_users au
   WHERE au.tenant_id = NEW.tenant_id
     AND au.status != 'deleted';

  IF v_current_count >= v_max_users THEN
    RAISE EXCEPTION
      'FIDEON_OS_LIMIT:SEATS Seat limit reached (%/%). Upgrade your plan to add more users.',
      v_current_count, v_max_users
    USING ERRCODE = 'P0001';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_tenant_seat_limit ON public.app_users;
CREATE TRIGGER trg_enforce_tenant_seat_limit
  BEFORE INSERT ON public.app_users
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_tenant_seat_limit();

DO $$
BEGIN
  RAISE NOTICE '✓ seat_limit_enforcement migration complete.';
END;
$$;
