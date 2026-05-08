-- ============================================================================
-- STANDALONE SEED — NOT included in all_migrations.sql
-- ============================================================================
-- Run manually in Supabase SQL Editor (role: postgres) AFTER schema migrations.
-- Do not place this file under supabase/migrations/ if you use build-all-migrations.ps1.
--
-- Tenant seed: Tenant_4 — professional plan, global_admin role.
-- User: Maksud Khan <maksud.khan@ideastoimpacts.com>
-- ============================================================================
--
-- HOW TO USE THIS SEED (self-hosted / staging)
-- ----------------------------------------------------------------------------
-- 1) Go to Dashboard → Authentication → Users → Add user
--    Email    : maksud.khan@ideastoimpacts.com
--    Password : Test@123
-- 2) Paste this entire script into the SQL Editor and click Run.
--    The script is fully idempotent — safe to re-run multiple times.
-- ============================================================================

DO $$
DECLARE
  -- ==================== CONFIG ====================
  c_seed_email              TEXT    := 'maksud.khan@ideastoimpacts.com';
  c_tenant_display_name     TEXT    := 'Tenant_4';
  c_full_name               TEXT    := 'Maksud Khan';
  c_plan                    TEXT    := 'professional';           -- starter | professional | enterprise
  c_workflow_addon_slots    INTEGER := 0;                        -- 0–5
  c_agent_packs             TEXT[]  := ARRAY['agentic-rag'];     -- Agentic RAG Add-On
  c_device_name             TEXT    := 'Maksud primary device';
  c_signup_wizard_version   TEXT    := 'v1';
  c_device_profile          JSONB   := jsonb_build_object(
    'device_name',                'Maksud primary device',
    'device_type',                'desktop',
    'os_name',                    'Windows',
    'os_version',                 '11',
    'app_version',                'web-1.0.0',
    'browser_name',               'Chrome',
    'browser_version',            '130',
    'locale',                     'en-US',
    'timezone',                   'UTC',
    'platform',                   'web',
    'user_agent',                 'seed/bootstrap',
    'hardware_fingerprint_sha256','',
    'captured_at',                to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    'source',                     'seed_migration'
  );
  -- ================================================

  v_user_id        UUID;
  v_email          TEXT;
  v_tenant_id      UUID;
  v_slug           TEXT;
  v_slug_norm      TEXT;
  v_max_packs      INTEGER;
  v_max_models     INTEGER;
  v_slots_total    INTEGER;
  v_addon          INTEGER;
  v_now            TIMESTAMPTZ := clock_timestamp();
  v_requested_role TEXT := 'global_admin';
BEGIN
  c_seed_email := lower(trim(c_seed_email));

  -- ── 1. Resolve the auth.users row ────────────────────────────────────────
  SELECT id, COALESCE(email, '')
  INTO v_user_id, v_email
  FROM auth.users
  WHERE lower(trim(email)) = c_seed_email
  LIMIT 1;

  IF v_user_id IS NULL THEN
    RAISE EXCEPTION
      'No auth.users row found for %. '
      'Go to Dashboard → Authentication → Users → Add user first, then re-run this script.',
      c_seed_email;
  END IF;

  RAISE NOTICE 'Found auth.users row: id=%', v_user_id;

  -- ── 2. Mark email as confirmed ───────────────────────────────────────────
  UPDATE auth.users
  SET
    email_confirmed_at   = COALESCE(email_confirmed_at, v_now),
    confirmation_token   = '',
    confirmation_sent_at = NULL
  WHERE id = v_user_id;

  UPDATE auth.identities
  SET
    identity_data = COALESCE(identity_data, '{}'::jsonb)
                    || jsonb_build_object('email_verified', true),
    updated_at    = v_now
  WHERE user_id = v_user_id
    AND provider = 'email';

  -- ── 3. Resolve plan limits ────────────────────────────────────────────────
  v_addon := GREATEST(0, LEAST(5, c_workflow_addon_slots));

  SELECT pl.max_agent_packs, pl.max_active_models
  INTO v_max_packs, v_max_models
  FROM public.plan_limits(c_plan) pl;

  v_slots_total := CASE c_plan
    WHEN 'enterprise'   THEN NULL
    WHEN 'professional' THEN 15 + v_addon
    ELSE                     3  + v_addon
  END;

  -- ── 4. Upsert tenant ─────────────────────────────────────────────────────
  SELECT id, slug
  INTO v_tenant_id, v_slug
  FROM public.tenants
  WHERE lower(trim(name)) = lower(trim(c_tenant_display_name))
  LIMIT 1;

  IF v_tenant_id IS NOT NULL THEN
    UPDATE public.tenants SET
      is_active            = true,
      plan                 = COALESCE(c_plan, 'starter'),
      tier                 = COALESCE(c_plan, 'starter'),
      agent_packs          = c_agent_packs,
      workflow_addon_slots = v_addon,
      workflow_slots_total = v_slots_total,
      max_agent_packs      = v_max_packs,
      max_active_models    = v_max_models,
      metadata             = COALESCE(metadata, '{}'::jsonb) || jsonb_strip_nulls(jsonb_build_object(
        'created_from_signup', true,
        'signup_user_id',      v_user_id,
        'plan',                c_plan,
        'seed_migration',      true
      ))
    WHERE id = v_tenant_id;
    RAISE NOTICE 'Updated existing tenant: id=%, slug=%', v_tenant_id, v_slug;
  ELSE
    v_slug_norm := lower(regexp_replace(c_tenant_display_name, '[^a-zA-Z0-9]+', '-', 'g'));
    v_slug_norm := trim(both '-' FROM v_slug_norm);
    IF v_slug_norm = '' THEN v_slug_norm := 'tenant'; END IF;
    v_slug := v_slug_norm || '-' || substring(replace(v_user_id::text, '-', ''), 1, 8);

    INSERT INTO public.tenants (
      slug, name, is_active, plan, tier, agent_packs,
      workflow_addon_slots, workflow_slots_total,
      max_agent_packs, max_active_models, metadata
    )
    VALUES (
      v_slug,
      c_tenant_display_name,
      true,
      COALESCE(c_plan, 'starter'),
      COALESCE(c_plan, 'starter'),
      c_agent_packs,
      v_addon,
      v_slots_total,
      v_max_packs,
      v_max_models,
      jsonb_strip_nulls(jsonb_build_object(
        'created_from_signup', true,
        'signup_user_id',      v_user_id,
        'plan',                c_plan,
        'seed_migration',      true
      ))
    )
    RETURNING id INTO v_tenant_id;
    RAISE NOTICE 'Created new tenant: id=%, slug=%', v_tenant_id, v_slug;
  END IF;

  -- ── 5. Upsert app_users ───────────────────────────────────────────────────
  INSERT INTO public.app_users (
    user_id, email, full_name, tenant_id, status, metadata
  )
  VALUES (
    v_user_id,
    COALESCE(v_email, ''),
    NULLIF(trim(c_full_name), ''),
    v_tenant_id,
    'active',
    jsonb_strip_nulls(jsonb_build_object(
      'onboarding_plan',                  c_plan,
      'onboarding_agent_packs',           to_jsonb(c_agent_packs),
      'onboarding_workflow_addon_slots',  v_addon,
      'onboarding_workflow_slots_total',  to_jsonb(v_slots_total),
      'onboarding_requested_role',        v_requested_role,
      'onboarding_signup_wizard_version', c_signup_wizard_version,
      'onboarding_device_name',           c_device_name,
      'onboarding_tenant_name',           c_tenant_display_name,
      'onboarding_device_profile',        c_device_profile,
      'seed_migration',                   true
    ))
  )
  ON CONFLICT (user_id) DO UPDATE SET
    email     = EXCLUDED.email,
    full_name = COALESCE(EXCLUDED.full_name, public.app_users.full_name),
    tenant_id = COALESCE(EXCLUDED.tenant_id, public.app_users.tenant_id),
    status    = 'active',
    metadata  = COALESCE(public.app_users.metadata, '{}'::jsonb) || EXCLUDED.metadata;

  RAISE NOTICE 'app_users upserted for user_id=%', v_user_id;

  -- ── 6. Upsert user_roles ──────────────────────────────────────────────────
  INSERT INTO public.user_roles (user_id, role)
  VALUES (v_user_id, 'global_admin'::public.app_role)
  ON CONFLICT (user_id) DO UPDATE SET role = EXCLUDED.role;

  RAISE NOTICE 'user_roles set to global_admin for user_id=%', v_user_id;

  -- ── 7. Sync raw_user_meta_data ────────────────────────────────────────────
  UPDATE auth.users
  SET raw_user_meta_data = COALESCE(raw_user_meta_data, '{}'::jsonb)
    || jsonb_strip_nulls(jsonb_build_object(
      'tenant_name',          c_tenant_display_name,
      'full_name',            NULLIF(trim(c_full_name), ''),
      'requested_role',       v_requested_role,
      'agent_packs',          to_jsonb(c_agent_packs),
      'device_name',          c_device_name,
      'signup_started_at',    to_char(v_now AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
      'signup_wizard_version',c_signup_wizard_version,
      'device_profile',       c_device_profile,
      'plan',                 c_plan,
      'workflow_addon_slots', v_addon,
      'max_agent_packs',      to_jsonb(v_max_packs),
      'max_active_models',    to_jsonb(v_max_models),
      'default_model_id',     NULL
    ))
  WHERE id = v_user_id;

  -- ── 8. Upsert device ─────────────────────────────────────────────────────
  IF c_device_name IS NOT NULL AND length(trim(c_device_name)) > 0 THEN
    IF NOT EXISTS (
      SELECT 1 FROM public.devices
      WHERE registered_by = v_user_id
        AND lower(trim(device_name)) = lower(trim(c_device_name))
    ) THEN
      INSERT INTO public.devices (
        device_name, device_token, registered_by, tenant_id,
        status, os_type, app_version, metadata
      )
      VALUES (
        trim(c_device_name),
        public.generate_device_token(),
        v_user_id,
        v_tenant_id,
        'never_checked_in',
        NULLIF(c_device_profile ->> 'os_name', ''),
        NULLIF(c_device_profile ->> 'app_version', ''),
        jsonb_strip_nulls(jsonb_build_object(
          'created_from_signup', true,
          'signup_user_id',      v_user_id,
          'device_profile',      c_device_profile,
          'seed_migration',      true
        ))
      );
      RAISE NOTICE 'Device registered: %', c_device_name;
    ELSE
      RAISE NOTICE 'Device already exists, skipped: %', c_device_name;
    END IF;
  END IF;

  RAISE NOTICE '=== SEED COMPLETE ===';
  RAISE NOTICE 'User    : % (%)', c_seed_email, v_user_id;
  RAISE NOTICE 'Tenant  : % (id=%, slug=%)', c_tenant_display_name, v_tenant_id, v_slug;
  RAISE NOTICE 'Role    : global_admin';
  RAISE NOTICE 'Plan    : %', c_plan;
END;
$$;
