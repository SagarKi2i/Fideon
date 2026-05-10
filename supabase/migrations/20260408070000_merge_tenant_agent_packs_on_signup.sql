-- ============================================================================
-- Migration: 20260408070000_merge_tenant_agent_packs_on_signup.sql
--
-- Signup hardening:
-- When a user signs up into an existing tenant, their chosen "agent_packs" must
-- never overwrite what the global admin already selected for the tenant.
--
-- Rule:
--   - For new tenant creation: tenant.agent_packs = requested_agent_packs
--   - For existing tenant: tenant.agent_packs = DISTINCT(tenant.agent_packs ∪ requested_agent_packs)
--   - Never remove packs via signup.
--
-- The tenant-level limit enforcement trigger (trg_enforce_tenant_agent_pack_limit)
-- remains the source of truth for max_agent_packs.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.handle_new_app_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  default_tenant_id          UUID;
  resolved_tenant_id         UUID;
  requested_tenant_name      TEXT;
  requested_plan             TEXT;
  requested_role             TEXT;
  requested_signup_version   TEXT;
  requested_device_name      TEXT;
  requested_device_profile   JSONB;
  requested_agent_packs      TEXT[];
  requested_addon_slots      INTEGER;
  resolved_slots_total       INTEGER;
  resolved_max_packs         INTEGER;
  resolved_max_models        INTEGER;
  normalized_slug            TEXT;
  generated_slug             TEXT;
BEGIN
  requested_tenant_name    := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'tenant_name',           '')), '');
  requested_plan           := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'plan',                  '')), '');
  requested_role           := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'requested_role',        '')), '');
  requested_signup_version := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'signup_wizard_version', '')), '');
  requested_device_name    := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'device_name',           '')), '');
  requested_device_profile := COALESCE(NEW.raw_user_meta_data -> 'device_profile', '{}'::jsonb);

  SELECT ARRAY(
    SELECT jsonb_array_elements_text(
      COALESCE(NEW.raw_user_meta_data -> 'agent_packs', '[]'::jsonb)
    )
  ) INTO requested_agent_packs;

  requested_agent_packs := COALESCE(requested_agent_packs, '{}'::text[]);

  requested_addon_slots := GREATEST(0, LEAST(5,
    COALESCE((NEW.raw_user_meta_data ->> 'workflow_addon_slots')::INTEGER, 0)
  ));

  IF requested_device_name IS NULL THEN
    requested_device_name := NULLIF(trim(COALESCE(requested_device_profile ->> 'device_name', '')), '');
  END IF;

  resolved_max_packs := COALESCE(
    (NEW.raw_user_meta_data ->> 'max_agent_packs')::INTEGER,
    (SELECT max_agent_packs FROM public.plan_limits(COALESCE(requested_plan, 'starter')))
  );
  resolved_max_models := COALESCE(
    (NEW.raw_user_meta_data ->> 'max_active_models')::INTEGER,
    (SELECT max_active_models FROM public.plan_limits(COALESCE(requested_plan, 'starter')))
  );
  resolved_slots_total := CASE
    WHEN requested_plan = 'enterprise'   THEN NULL
    WHEN requested_plan = 'professional' THEN 15 + requested_addon_slots
    ELSE                                      3  + requested_addon_slots
  END;

  SELECT id INTO default_tenant_id
  FROM public.tenants WHERE slug = 'default-tenant' LIMIT 1;
  resolved_tenant_id := default_tenant_id;

  IF requested_tenant_name IS NOT NULL THEN
    SELECT id INTO resolved_tenant_id
    FROM public.tenants
    WHERE is_active = true
      AND lower(trim(name)) = lower(trim(requested_tenant_name))
    ORDER BY created_at ASC, id ASC
    LIMIT 1;

    IF resolved_tenant_id IS NULL THEN
      normalized_slug := lower(regexp_replace(requested_tenant_name, '[^a-zA-Z0-9]+', '-', 'g'));
      normalized_slug := trim(both '-' FROM normalized_slug);
      IF normalized_slug = '' THEN normalized_slug := 'tenant'; END IF;
      generated_slug := normalized_slug || '-' || substring(replace(NEW.id::text, '-', ''), 1, 8);

      INSERT INTO public.tenants (
        slug, name, is_active,
        plan, tier,
        agent_packs, workflow_addon_slots, workflow_slots_total,
        max_agent_packs, max_active_models,
        metadata
      )
      VALUES (
        generated_slug,
        requested_tenant_name,
        true,
        COALESCE(requested_plan, 'starter'),
        COALESCE(requested_plan, 'starter'),
        requested_agent_packs,
        requested_addon_slots,
        resolved_slots_total,
        resolved_max_packs,
        resolved_max_models,
        jsonb_strip_nulls(jsonb_build_object(
          'created_from_signup', true,
          'signup_user_id',      NEW.id,
          'plan',                requested_plan
        ))
      )
      ON CONFLICT (slug) DO UPDATE SET
        name                 = EXCLUDED.name,
        plan                 = EXCLUDED.plan,
        tier                 = EXCLUDED.tier,
        agent_packs          = EXCLUDED.agent_packs,
        workflow_addon_slots = EXCLUDED.workflow_addon_slots,
        workflow_slots_total = EXCLUDED.workflow_slots_total,
        max_agent_packs      = EXCLUDED.max_agent_packs,
        max_active_models    = EXCLUDED.max_active_models,
        metadata             = COALESCE(public.tenants.metadata, '{}'::jsonb) || EXCLUDED.metadata
      RETURNING id INTO resolved_tenant_id;
    ELSE
      -- Existing tenant: only ADD packs, never overwrite/remove.
      UPDATE public.tenants SET
        agent_packs = (
          SELECT ARRAY(
            SELECT DISTINCT p
            FROM unnest(COALESCE(agent_packs, '{}'::text[]) || requested_agent_packs) AS p
          )
        ),
        -- Do not let signup change plan/tier/limits; keep admin-selected values.
        workflow_addon_slots = workflow_addon_slots,
        workflow_slots_total = workflow_slots_total,
        max_agent_packs      = max_agent_packs,
        max_active_models    = max_active_models
      WHERE id = resolved_tenant_id;
    END IF;
  END IF;

  INSERT INTO public.app_users (user_id, email, full_name, tenant_id, status, metadata)
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    NULLIF(NEW.raw_user_meta_data ->> 'full_name', ''),
    resolved_tenant_id,
    'active',
    jsonb_strip_nulls(jsonb_build_object(
      'onboarding_plan',                  requested_plan,
      'onboarding_agent_packs',           to_jsonb(requested_agent_packs),
      'onboarding_workflow_addon_slots',  requested_addon_slots,
      'onboarding_workflow_slots_total',  resolved_slots_total,
      'onboarding_requested_role',        requested_role,
      'onboarding_signup_wizard_version', requested_signup_version,
      'onboarding_device_name',           requested_device_name,
      'onboarding_tenant_name',           requested_tenant_name,
      'onboarding_device_profile',        requested_device_profile
    ))
  )
  ON CONFLICT (user_id) DO UPDATE
  SET
    email      = EXCLUDED.email,
    full_name  = COALESCE(EXCLUDED.full_name, public.app_users.full_name),
    tenant_id  = COALESCE(EXCLUDED.tenant_id, public.app_users.tenant_id),
    metadata   = COALESCE(public.app_users.metadata, '{}'::jsonb) || EXCLUDED.metadata;

  IF requested_device_name IS NOT NULL THEN
    INSERT INTO public.devices (
      device_name, device_token, registered_by, tenant_id, status,
      os_type, app_version, metadata
    )
    VALUES (
      requested_device_name,
      public.generate_device_token(),
      NEW.id,
      resolved_tenant_id,
      'never_checked_in',
      NULLIF(requested_device_profile ->> 'os_name',    ''),
      NULLIF(requested_device_profile ->> 'app_version',''),
      jsonb_strip_nulls(jsonb_build_object(
        'created_from_signup', true,
        'signup_user_id',      NEW.id,
        'device_profile',      requested_device_profile
      ))
    )
    ON CONFLICT DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  RAISE NOTICE '✓ merge_tenant_agent_packs_on_signup migration complete.';
END;
$$;

