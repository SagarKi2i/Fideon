-- Webhook delivery engine tables (FNF-68)
-- Tables: webhooks, webhook_events, webhook_deliveries, webhook_secrets
-- All access goes through the backend service role.
-- RLS is enabled on every table; the only policy grants service_role full access.

-- ────────────────────────────────────────────────────────────────
-- 1. webhooks
--    One row per registered endpoint. Holds URL, subscribed event
--    list, and activation flag.
-- ────────────────────────────────────────────────────────────────
create table if not exists public.webhooks (
  id           uuid        primary key default gen_random_uuid(),
  tenant_id    uuid        not null,
  url          text        not null check (length(url) <= 2048),
  description  text,
  events       jsonb       not null default '[]'::jsonb,
  is_active    boolean     not null default true,
  created_by   uuid,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index if not exists webhooks_tenant_active_idx
  on public.webhooks (tenant_id, is_active);

alter table public.webhooks enable row level security;

-- Service role (backend) gets full CRUD; no other principal should touch this.
drop policy if exists "service_role_all_webhooks" on public.webhooks;
create policy "service_role_all_webhooks"
  on public.webhooks
  for all
  to service_role
  using (true)
  with check (true);

-- Keep updated_at in sync.
drop trigger if exists set_webhooks_updated_at on public.webhooks;
create trigger set_webhooks_updated_at
  before update on public.webhooks
  for each row
  execute function public.set_updated_at();


-- ────────────────────────────────────────────────────────────────
-- 2. webhook_events
--    Durable log of every event emitted into the system.
--    The delivery worker fans these out to matching webhook_deliveries.
-- ────────────────────────────────────────────────────────────────
create table if not exists public.webhook_events (
  id           uuid        primary key default gen_random_uuid(),
  tenant_id    uuid        not null,
  event_type   text        not null,
  payload      jsonb       not null default '{}'::jsonb,
  created_at   timestamptz not null default now()
);

create index if not exists webhook_events_tenant_type_idx
  on public.webhook_events (tenant_id, event_type, created_at desc);

alter table public.webhook_events enable row level security;

drop policy if exists "service_role_all_webhook_events" on public.webhook_events;
create policy "service_role_all_webhook_events"
  on public.webhook_events
  for all
  to service_role
  using (true)
  with check (true);


-- ────────────────────────────────────────────────────────────────
-- 3. webhook_deliveries
--    One row per (event × webhook endpoint) delivery attempt.
--    The worker polls status='pending' rows whose next_attempt_at
--    is in the past.
-- ────────────────────────────────────────────────────────────────
create table if not exists public.webhook_deliveries (
  id               uuid        primary key default gen_random_uuid(),
  tenant_id        uuid        not null,
  webhook_id       uuid        not null references public.webhooks (id) on delete cascade,
  event_id         uuid        not null references public.webhook_events (id) on delete cascade,
  status           text        not null default 'pending'
                               check (status in ('pending', 'delivered', 'failed', 'dead_letter')),
  attempt_count    integer     not null default 0,
  next_attempt_at  timestamptz not null default now(),
  last_attempt_at  timestamptz,
  delivered_at     timestamptz,
  response_status  integer,
  response_body    text,
  last_error       text,
  created_at       timestamptz not null default now()
);

-- Worker query: pending rows due for delivery, ordered oldest-first.
create index if not exists webhook_deliveries_pending_due_idx
  on public.webhook_deliveries (status, next_attempt_at asc)
  where status = 'pending';

-- Lookup by webhook for delivery history UI.
create index if not exists webhook_deliveries_webhook_idx
  on public.webhook_deliveries (webhook_id, created_at desc);

-- Lookup by event (fan-out audit).
create index if not exists webhook_deliveries_event_idx
  on public.webhook_deliveries (event_id);

alter table public.webhook_deliveries enable row level security;

drop policy if exists "service_role_all_webhook_deliveries" on public.webhook_deliveries;
create policy "service_role_all_webhook_deliveries"
  on public.webhook_deliveries
  for all
  to service_role
  using (true)
  with check (true);


-- ────────────────────────────────────────────────────────────────
-- 4. webhook_secrets
--    One row per active signing secret per webhook.
--    Only one row should have is_active=true per webhook at any time
--    (enforced by application logic on rotation).
--    Secret is stored as:
--      - encrypted_secret: Fernet-encrypted plaintext (for signing)
--      - secret_hash: SHA-256 hex (for fast verification without decryption)
--    The plaintext is NEVER stored or logged.
-- ────────────────────────────────────────────────────────────────
create table if not exists public.webhook_secrets (
  id                uuid        primary key default gen_random_uuid(),
  tenant_id         uuid        not null,
  webhook_id        uuid        not null references public.webhooks (id) on delete cascade,
  secret_hash       text        not null,
  encrypted_secret  text        not null,
  is_active         boolean     not null default true,
  created_at        timestamptz not null default now()
);

create index if not exists webhook_secrets_webhook_active_idx
  on public.webhook_secrets (webhook_id, is_active)
  where is_active = true;

alter table public.webhook_secrets enable row level security;

drop policy if exists "service_role_all_webhook_secrets" on public.webhook_secrets;
create policy "service_role_all_webhook_secrets"
  on public.webhook_secrets
  for all
  to service_role
  using (true)
  with check (true);
