# Production Runbook: Onboarding + Tenant Provisioning

## Scope
- `POST /api/v1/tenants` provisioning flow
- Signup wizard metadata persistence and first-model activation
- Tenant-scope access controls in shared-schema deployment

## Pre-Deploy Checklist
- Apply all migrations, including:
  - `20260313002000_signup_device_profile_persistence.sql`
  - `20260317100000_tenant_scope_rls_hardening.sql`
- Confirm backend env vars are present:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `SUPABASE_ANON_KEY`
  - `DEVICE_JWT_SECRET`
- Confirm CI passed:
  - `tests/test_device_v1_production.py`
  - `tests/test_tenants_production.py`
  - `tests/test_tenant_provisioning_sla.py`

## Post-Deploy Smoke Tests
- Route exposure:
  - `GET /openapi.json` contains `/api/v1/tenants`
- Auth guard:
  - unauthenticated `POST /api/v1/tenants` returns `401`
- Method guard:
  - `GET /api/v1/tenants` returns `405`
- Happy path (admin bearer token):
  - `POST /api/v1/tenants` returns `201` and tenant/admin payload

## Operational SLO/SLA Signals
- Tenant provisioning warm-path response time target: p95 `< 3s`
- Error budget focus:
  - 4xx spikes for validation/auth misconfiguration
  - 5xx spikes for rollback failures or Supabase connectivity
- Alert if rollback failure log appears:
  - event name: `tenants.rollback_failed`

## Incident Response
1. Identify failure stage from structured logs (`tenants.create.*` events).
2. Verify whether rollback completed:
   - tenant row presence in `tenants`
   - auth user presence in Supabase Auth
3. If incomplete rollback:
   - manually remove orphaned tenant or auth user
   - re-run provisioning with a new idempotency key
4. Document incident with request id and tenant/admin identifiers.

## Safe Rollback Plan
- Roll back backend deployment to last known good image.
- Keep DB migration `20260317100000_tenant_scope_rls_hardening.sql` unless it causes access regression.
- If RLS regression occurs, apply emergency policy patch migration (do not mutate historical migration files).

## Change Management Notes
- Keep shared-schema model; tenant isolation enforced by RLS and API scoping.
- Treat global admin as cross-tenant operator; tenant admin remains tenant-bounded.
