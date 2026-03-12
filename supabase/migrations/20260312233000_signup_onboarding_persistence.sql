-- Persist full onboarding metadata from auth signup into application tables.
-- This migration extends the existing auth.users -> app_users trigger logic.

CREATE OR REPLACE FUNCTION public.handle_new_app_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  default_tenant_id UUID;
  resolved_tenant_id UUID;
  requested_tenant_name TEXT;
  requested_plan TEXT;
  requested_model_id TEXT;
  requested_device_name TEXT;
  normalized_slug TEXT;
  generated_slug TEXT;
  resolved_model_name TEXT;
  resolved_domain public.model_domain;
BEGIN
  -- Metadata sent from signup wizard
  requested_tenant_name := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'tenant_name', '')), '');
  requested_plan := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'plan', '')), '');
  requested_model_id := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'default_model_id', '')), '');
  requested_device_name := NULLIF(trim(COALESCE(NEW.raw_user_meta_data ->> 'device_name', '')), '');

  SELECT id INTO default_tenant_id
  FROM public.tenants
  WHERE slug = 'default-tenant'
  LIMIT 1;

  resolved_tenant_id := default_tenant_id;

  -- Create a tenant for the user when tenant_name is provided.
  IF requested_tenant_name IS NOT NULL THEN
    normalized_slug := lower(regexp_replace(requested_tenant_name, '[^a-zA-Z0-9]+', '-', 'g'));
    normalized_slug := trim(both '-' FROM normalized_slug);
    IF normalized_slug = '' THEN
      normalized_slug := 'tenant';
    END IF;

    generated_slug := normalized_slug || '-' || substring(replace(NEW.id::text, '-', ''), 1, 8);

    INSERT INTO public.tenants (slug, name, is_active, metadata)
    VALUES (
      generated_slug,
      requested_tenant_name,
      true,
      jsonb_strip_nulls(
        jsonb_build_object(
          'created_from_signup', true,
          'signup_user_id', NEW.id,
          'plan', requested_plan
        )
      )
    )
    ON CONFLICT (slug) DO UPDATE
    SET
      name = EXCLUDED.name,
      metadata = COALESCE(public.tenants.metadata, '{}'::jsonb) || EXCLUDED.metadata
    RETURNING id INTO resolved_tenant_id;
  END IF;

  -- Upsert app user profile and persist onboarding metadata.
  INSERT INTO public.app_users (user_id, email, full_name, tenant_id, status, metadata)
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    NULLIF(NEW.raw_user_meta_data ->> 'full_name', ''),
    resolved_tenant_id,
    'active',
    jsonb_strip_nulls(
      jsonb_build_object(
        'onboarding_plan', requested_plan,
        'onboarding_default_model_id', requested_model_id,
        'onboarding_device_name', requested_device_name,
        'onboarding_tenant_name', requested_tenant_name
      )
    )
  )
  ON CONFLICT (user_id) DO UPDATE
  SET
    email = EXCLUDED.email,
    full_name = COALESCE(EXCLUDED.full_name, public.app_users.full_name),
    tenant_id = COALESCE(EXCLUDED.tenant_id, public.app_users.tenant_id),
    metadata = COALESCE(public.app_users.metadata, '{}'::jsonb) || EXCLUDED.metadata;

  -- Auto-activate selected model when provided.
  IF requested_model_id IS NOT NULL THEN
    SELECT mc.model_name, mc.domain::public.model_domain
      INTO resolved_model_name, resolved_domain
    FROM public.model_catalog mc
    WHERE mc.model_id = requested_model_id
      AND mc.is_active = true
    LIMIT 1;

    -- Fallbacks for onboarding model ids when catalog row is absent.
    IF resolved_model_name IS NULL THEN
      resolved_model_name := CASE requested_model_id
        WHEN 'quote-generation' THEN 'Quote Generation Agent'
        WHEN 'policy-comparison' THEN 'Policy Comparison Engine'
        WHEN 'document-retrieval' THEN 'Document Retrieval'
        WHEN 'claims-fnol' THEN 'Claims and FNOL Intelligence'
        WHEN 'coverage-validation' THEN 'Coverage Validation and Eligibility'
        ELSE initcap(replace(requested_model_id, '-', ' '))
      END;
    END IF;

    IF resolved_domain IS NULL THEN
      resolved_domain := 'insurance'::public.model_domain;
    END IF;

    INSERT INTO public.activated_models (user_id, model_id, model_name, domain)
    VALUES (NEW.id, requested_model_id, resolved_model_name, resolved_domain)
    ON CONFLICT (user_id, model_id) DO NOTHING;
  END IF;

  -- Create first device record with generated device token.
  IF requested_device_name IS NOT NULL THEN
    INSERT INTO public.devices (device_name, device_token, registered_by, status, metadata)
    VALUES (
      requested_device_name,
      public.generate_device_token(),
      NEW.id,
      'never_checked_in',
      jsonb_build_object('created_from_signup', true, 'signup_user_id', NEW.id)
    );
  END IF;

  RETURN NEW;
END;
$$;
