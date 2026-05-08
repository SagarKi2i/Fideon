-- ============================================================================
-- Migration: 20260408090000_tenant_signup_config_exact_lookup_rpc.sql
--
-- Production hardening: deterministic tenant lookup for signup wizard.
--
-- The Signup wizard must resolve the tenant deterministically using the same
-- normalization strategy as the DB trigger:
--   lower(trim(tenants.name)) = lower(trim(requested_tenant_name))
--
-- Exposes a JSONB payload for:
--   - tenant plan lock
--   - agent pack preselection + remaining pack slots
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_tenant_signup_config_exact(p_tenant_name TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_normalized_name TEXT := lower(trim(p_tenant_name));
  v_tenants_rec RECORD;
  v_packs TEXT[];
  v_max_packs INTEGER;
  v_remaining INTEGER;
BEGIN
  IF v_normalized_name IS NULL OR v_normalized_name = '' THEN
    RETURN NULL;
  END IF;

  SELECT
    id,
    slug,
    name,
    plan,
    max_agent_packs,
    COALESCE(agent_packs, '{}'::text[]) AS agent_packs,
    COALESCE(workflow_addon_slots, 0) AS workflow_addon_slots,
    workflow_slots_total
  INTO v_tenants_rec
  FROM public.tenants
  WHERE is_active = true
    AND lower(trim(name)) = v_normalized_name
  ORDER BY created_at ASC, id ASC
  LIMIT 1;

  IF v_tenants_rec.id IS NULL THEN
    RETURN NULL;
  END IF;

  v_packs := v_tenants_rec.agent_packs;
  v_max_packs := v_tenants_rec.max_agent_packs;

  IF v_max_packs IS NULL THEN
    v_remaining := NULL; -- unlimited
  ELSE
    v_remaining := GREATEST(0, v_max_packs - COALESCE(cardinality(v_packs), 0));
  END IF;

  RETURN jsonb_build_object(
    'tenant', jsonb_build_object(
      'id', v_tenants_rec.id,
      'slug', v_tenants_rec.slug,
      'name', v_tenants_rec.name
    ),
    'plan', COALESCE(v_tenants_rec.plan, 'starter'),
    'agent_packs', v_packs,
    'max_agent_packs', v_max_packs,
    'remaining_pack_slots', v_remaining,
    'workflow_addon_slots', v_tenants_rec.workflow_addon_slots,
    'workflow_slots_total', v_tenants_rec.workflow_slots_total
  );
END;
$$;

