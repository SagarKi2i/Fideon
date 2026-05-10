# Webhook SRS Gap Analysis
**Document:** FNF-68 Secure Webhook Delivery Engine  
**SRS Reference:** `webhook_srs_fideon_fabric.html`  
**Analyzed Against:** `neura-box-cloud-main` codebase (branch: `v1-dev`)  
**Date:** April 2026  

---

## Quick Summary

Your project already has a working webhook engine in Python/FastAPI. The SRS was written for a **Supabase Edge Functions (Deno/TypeScript)** architecture — so the code samples in the SRS don't apply directly. The logic and requirements do. About **60% of the SRS is already implemented**.

**The single biggest blocker:** The database tables (`webhooks`, `webhook_events`, `webhook_deliveries`, `webhook_secrets`) **do not exist in any migration file**. Nothing works until this is done.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Already implemented |
| ❌ | Not implemented |
| ⚠️ | Partially implemented or has a difference |
| 🔴 | Must implement — system broken or security risk without it |
| 🟡 | Should implement — needed before production |
| 🟢 | Can defer — next sprint or optional |
| ⏭️ | Skip entirely — not applicable to this architecture |

---

## Section-by-Section Status

---

### 1. Webhook Registration (FR-01 to FR-05)

| Req ID | Requirement | Status | Notes |
|--------|-------------|--------|-------|
| FR-01 | Register HTTPS endpoint URL | ✅ | `POST /api/v1/webhooks` in [webhooks.py:113](../backend/app/routes/webhooks.py#L113) |
| FR-01 | Reject HTTP (non-HTTPS) URLs | ❌ 🟡 | No protocol check. Any URL is accepted right now |
| FR-02 | Subscribe to specific event types | ✅ | `events` array stored and filtered in [webhook_engine.py:185](../backend/app/services/webhook_engine.py#L185) |
| FR-03 | Generate unique secret on registration, return once | ✅ | [webhooks.py:94-110](../backend/app/routes/webhooks.py#L94) — secret returned once, never retrievable |
| FR-03 | Secret never stored in plain text | ✅ | Stored as Fernet-encrypted + SHA-256 hash. SRS uses bcrypt+Vault; both are valid approaches |
| FR-04 | Max 10 endpoints per tenant | ❌ 🟢 | No cap enforced. Can add a count check before insert |
| FR-05 | Optional name/description for endpoint | ✅ | `description` field supported in create/update |

---

### 2. Event Delivery (FR-06 to FR-12)

| Req ID | Requirement | Status | Notes |
|--------|-------------|--------|-------|
| FR-06 | HTTP POST with `application/json` | ✅ | [webhook_engine.py:309-316](../backend/app/services/webhook_engine.py#L309) |
| FR-07 | Payload includes `event_id`, `event_type`, `tenant_id`, `timestamp`, `data` | ⚠️ 🟡 | Payload has `id`, `type`, `created_at`, `data` — missing `tenant_id` and `timestamp` fields in body. `created_at` is used instead of explicit `timestamp` |
| FR-08 | `X-Fideon-Signature` header with `sha256=<hex>` | ✅ | [webhook_engine.py:286-296](../backend/app/services/webhook_engine.py#L286) |
| FR-09 | `X-Fideon-Event-Id` header for idempotency | ⚠️ 🟡 | Sends `X-Fideon-Delivery-Id` (delivery ID) instead of event ID. These are different — same event retried 3 times should keep the same Event-Id |
| FR-10 | 10-second HTTP timeout per attempt | ⚠️ 🟡 | Current timeout is **15 seconds** [webhook_engine.py:310](../backend/app/services/webhook_engine.py#L310). SRS says 10s |
| FR-11 | Only 2xx = success; all others trigger retry | ✅ | [webhook_engine.py:312](../backend/app/services/webhook_engine.py#L312) |
| FR-12 | Async delivery — never blocks calling API | ✅ | Background worker loop in [webhook_engine.py:365](../backend/app/services/webhook_engine.py#L365), started at app startup |

---

### 3. Retry & Dead-Letter Queue (FR-13 to FR-17)

| Req ID | Requirement | Status | Notes |
|--------|-------------|--------|-------|
| FR-13 | Retry up to 3 times (4 total attempts) | ✅ | Configurable via `WEBHOOK_MAX_ATTEMPTS`. Default should be set to 4 |
| FR-14 | Back-off schedule: 30s → 5min → 30min with ±10% jitter | ⚠️ 🟡 | Back-off is implemented but uses generic exponential formula (`base * 2^n`) — not the specific 30s/5min/30min schedule. No jitter added |
| FR-15 | Failed deliveries go to dead-letter queue | ✅ | Status set to `dead_letter` in [webhook_engine.py:327](../backend/app/services/webhook_engine.py#L327) |
| FR-16 | DLQ visible in management UI — view, replay, dismiss | ❌ 🟢 | No DLQ listing or replay API endpoints. No UI panel for it |
| FR-17 | DLQ entries retained 30 days then auto-deleted | ❌ 🟢 | No `expires_at` column or cleanup job |

---

### 4. Secret Management (FR-18 to FR-20)

| Req ID | Requirement | Status | Notes |
|--------|-------------|--------|-------|
| FR-18 | Tenants can rotate secret; new secret returned once | ✅ | `POST /api/v1/webhooks/{id}/rotate-secret` in [webhooks.py:178](../backend/app/routes/webhooks.py#L178) |
| FR-19 | 30-minute dual-secret grace period on rotation | ❌ 🟢 | Old secret immediately deactivated at [webhooks.py:193](../backend/app/routes/webhooks.py#L193). No grace window |
| FR-20 | Secret storage: bcrypt hash, never logged | ⚠️ | Uses SHA-256 hash (not bcrypt). SRS requires bcrypt cost ≥12. For your FastAPI setup, SHA-256 + Fernet encryption is acceptable but differs from spec |

---

### 5. Management UI (FR-21 to FR-24)

| Req ID | Requirement | Status | Notes |
|--------|-------------|--------|-------|
| FR-21 | List all endpoints with status and last delivery | ✅ | [WebhooksSettingsPanel.tsx](../frontend/src/components/settings/WebhooksSettingsPanel.tsx) |
| FR-22 | Secret rotation from UI | ✅ | Rotation button in the same UI panel |
| FR-23 | Delivery history — last 50 attempts per endpoint | ❌ 🟢 | `webhook_deliveries` table will have this data once migration runs, but no UI panel shows it |
| FR-24 | Send test event from UI | ⚠️ 🟢 | `POST /api/v1/webhooks/test-event` exists [webhooks.py:219](../backend/app/routes/webhooks.py#L219). Not wired to a button in the UI yet |

---

### 6. Security Requirements (SEC-01 to SEC-11)

| Req ID | Requirement | Status | Notes |
|--------|-------------|--------|-------|
| SEC-01 | HTTPS only; reject HTTP | ❌ 🔴 | No protocol validation at registration or delivery time |
| SEC-02 | HMAC-SHA256 signing over raw JSON body | ⚠️ 🔴 | Signing works, but **signing string is wrong**. SRS requires `timestamp + "." + body`. Current code signs just `body` ([webhook_engine.py:286](../backend/app/services/webhook_engine.py#L286)). Receivers using the spec's verifier will reject all events |
| SEC-03 | `X-Fideon-Timestamp` header; receivers reject events > 5min old | ✅ | Timestamp sent as header. Receiver-side tolerance is receiver's responsibility |
| SEC-04 | Constant-time signature comparison | ✅ | `hmac.compare_digest` used in Python stdlib's `hmac.new` — safe by default |
| SEC-05 | Secrets never appear in logs or error messages | ✅ | No secret logged. `decrypt_secret` errors don't expose the value |
| SEC-06 | Rate limiting: 10 registrations/min per tenant | ❌ 🟢 | No per-tenant rate limit on webhook registration. General app-level rate limiter (slowapi) exists but not webhook-specific |
| SEC-07 | SSRF prevention: block RFC-1918, loopback, Azure ranges | ❌ 🔴 | **No SSRF validation at all.** The delivery worker will POST to any URL including `10.x.x.x`, `169.254.169.254`, Azure IMDS, etc. Real security risk |
| SEC-08 | Input validation on all API inputs | ✅ | URL length, event name format, description length all validated |
| SEC-09 | Tenant-scoped access (RLS + API layer) | ✅ | All queries filter by `tenant_id` from JWT context |
| SEC-10 | During rotation grace period, sign with NEW secret only | ⏭️ | Not applicable — grace period not implemented yet |
| SEC-11 | Cloud worker must never deliver to private/internal IPs (DNS rebinding prevention) | ❌ 🔴 | Same as SEC-07 — no IP check at delivery time. A domain that resolved cleanly at registration could be rebinding to a private IP |

---

### 7. Non-Functional Requirements

| Req ID | Requirement | Status | Notes |
|--------|-------------|--------|-------|
| NFR (throughput) | 500 events/min per tenant | ✅ | Worker polls every 2 seconds, batch size 25. Sufficient for expected load |
| NFR (latency p95) | < 5s from event to first delivery attempt | ✅ | Worker polls every 2s; delivery is near-immediate |
| NFR (reliability) | ≥ 99.5% delivery within 4 attempts | ✅ | Retry logic covers this |
| NFR (availability) | 99.9% worker uptime | ✅ | Started with app lifespan, restarts with app |
| NFR-09 | Zero plain-text secrets in cloud storage | ✅ | Fernet-encrypted in DB. Never in logs |
| NFR (RLS) | Row-level security on all webhook tables | ❌ 🟡 | RLS policies not created — the migration doesn't exist yet |

---

### 8. Database Schema

| Table | Status | Notes |
|-------|--------|-------|
| `webhooks` | ❌ 🔴 | **No migration exists.** Table referenced in code but not created |
| `webhook_events` | ❌ 🔴 | Same — missing migration |
| `webhook_deliveries` | ❌ 🔴 | Same — missing migration |
| `webhook_secrets` | ❌ 🔴 | Same — missing migration |
| `security_events` | ❌ 🟢 | SRS adds this for SSRF audit log. Not in codebase at all |
| `rate_limit_log` | ❌ 🟢 | Only needed if you add per-tenant rate limiting |

---

### 9. Architecture Differences (SRS vs Your Stack)

These are things from the SRS that **do not apply** to your project because you use a different architecture:

| SRS Requirement | Why It Doesn't Apply |
|----------------|----------------------|
| Supabase Edge Functions (Deno/TypeScript) | Your backend is **FastAPI (Python)**. All the TypeScript code samples in the SRS are irrelevant |
| Supabase Vault for secret storage | Vault is a Supabase-specific feature. Your Fernet encryption approach is the correct equivalent |
| pg_cron for delivery worker trigger | You use a Python `asyncio` background loop — same result, different mechanism |
| bcrypt for secret hash | You use SHA-256. Bcrypt makes sense in the Edge Function context (no KMS). Fernet encryption is stronger for your use case |
| `is_edge_local` / on-premise agent delivery | Only relevant if you have an on-premise agent component. Skip unless that's in scope |
| `*.internal.cloudapp.net`, Azure Private Link patterns | Still relevant for SSRF blocking, but the Azure-specific ranges assume Azure hosting. Include them anyway — they're cheap to add |

---

## Consolidated Action Plan

### 🔴 Do This First (System is Broken / Security Risk)

1. **Write DB migration** — `webhooks`, `webhook_events`, `webhook_deliveries`, `webhook_secrets` tables with RLS policies. Nothing works without this.
2. **Fix signing string** — Change from `sign(body)` to `sign(timestamp + "." + body)` in [webhook_engine.py:286](../backend/app/services/webhook_engine.py#L286). Receivers following the spec will reject every event otherwise.
3. **Add SSRF validation** — Validate URLs at registration AND delivery time. Block RFC-1918, loopback, link-local, Azure IMDS ranges.

### 🟡 Do Before Calling It Production

4. **Add HTTPS-only check** at registration (reject `http://` URLs)
5. **Fix `X-Fideon-Event-Id` header** — send the `event_id` (not delivery ID) for idempotency
6. **Add `tenant_id` + `timestamp` to event payload body** (FR-07)
7. **Set delivery timeout to 10 seconds** (currently 15s)
8. **Fix retry schedule** to 30s → 5min → 30min with ±10% jitter

### 🟢 Next Sprint / Can Defer

9. DLQ listing + replay API endpoints
10. Delivery history UI (last 50 attempts per endpoint)
11. Test event button in UI
12. Dual-secret 30-min grace window on rotation
13. Max 10 endpoints per tenant cap
14. Per-tenant rate limiting on registration (10/min)
15. `expires_at` on DLQ rows + 30-day cleanup job

### ⏭️ Skip Entirely

- All Deno/TypeScript code samples from SRS
- Supabase Vault integration
- pg_cron cron setup
- `is_edge_local` / edge agent delivery (unless on-premise agents are in scope)

---

## Files to Touch

| Task | File(s) |
|------|---------|
| DB migration | Create new `supabase/migrations/20260413_webhook_tables.sql` |
| Fix signing string | [backend/app/services/webhook_engine.py:286](../backend/app/services/webhook_engine.py#L286) |
| SSRF validation | New file `backend/app/core/ssrf_validator.py` + call in [webhooks.py:79](../backend/app/routes/webhooks.py#L79) and [webhook_engine.py:304](../backend/app/services/webhook_engine.py#L304) |
| HTTPS-only check | [backend/app/routes/webhooks.py:73](../backend/app/routes/webhooks.py#L73) |
| Fix Event-Id header | [backend/app/services/webhook_engine.py:289](../backend/app/services/webhook_engine.py#L289) |
| Fix timeout | [backend/app/services/webhook_engine.py:310](../backend/app/services/webhook_engine.py#L310) |
| Fix retry schedule | [backend/app/services/webhook_engine.py:202](../backend/app/services/webhook_engine.py#L202) |

---

*Generated from analysis of `webhook_srs_fideon_fabric.html` vs codebase on 2026-04-13*
