-- Audit log table for auth activity (logins, logouts, approvals, etc.)

create table if not exists public.auth_audit (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null
);

-- Ensure expected columns exist even if table was created earlier
alter table public.auth_audit
  add column if not exists email text;

alter table public.auth_audit
  add column if not exists role text;

alter table public.auth_audit
  add column if not exists event text;

alter table public.auth_audit
  add column if not exists created_at timestamptz not null default now();

-- Normalized ATNA-style fields
-- action_code: C=Create, R=Read, U=Update, D=Delete, E=Execute
alter table public.auth_audit
  add column if not exists action_code text;

-- outcome_code: 0=Success, 4=Minor failure, 8=Serious, 12=Major
alter table public.auth_audit
  add column if not exists outcome_code integer;

alter table public.auth_audit
  add column if not exists resource_type text;

alter table public.auth_audit
  add column if not exists resource_id text;

-- Integrity hash for tamper-evidence (no PII). Hash is computed over:
-- user_id, role, event, action_code, outcome_code, resource_type, resource_id, created_at
alter table public.auth_audit
  add column if not exists integrity_hash text;

alter table public.auth_audit enable row level security;

-- Users can insert their own audit rows
create policy if not exists "Users can insert their own auth audit"
on public.auth_audit
for insert
with check (auth.uid() = user_id);

-- Users see only their own activity
create policy if not exists "Users see own auth audit"
on public.auth_audit
for select
using (user_id = auth.uid());

-- Admins can see user + admin + viewer + guest activity (but not global_admin)
create policy if not exists "Admins see user+admin auth audit"
on public.auth_audit
for select
using (
  public.has_role(auth.uid(), 'admin'::public.app_role)
  and role in ('admin', 'user', 'viewer', 'guest')
);

-- Global admins can see all audit activity
create policy if not exists "Global admins see all auth audit"
on public.auth_audit
for select
using (
  public.has_role(auth.uid(), 'global_admin'::public.app_role)
);

