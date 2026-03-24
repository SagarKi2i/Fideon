-- Persistent per-user realtime notification inbox for bell + read/clear state.

create table if not exists public.user_notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  table_name text not null check (table_name in ('pod_activation_requests', 'device_sync_logs', 'decision_reviews')),
  event_type text not null check (event_type in ('INSERT', 'UPDATE', 'DELETE')),
  message text not null,
  target_path text null,
  source_fingerprint text not null,
  created_at timestamptz not null default now(),
  read_at timestamptz null
);

create index if not exists idx_user_notifications_user_created
  on public.user_notifications (user_id, created_at desc);

create index if not exists idx_user_notifications_user_unread
  on public.user_notifications (user_id, read_at);

create index if not exists idx_user_notifications_dedupe
  on public.user_notifications (user_id, source_fingerprint, created_at desc);

alter table public.user_notifications enable row level security;

drop policy if exists "user_notifications_select_own" on public.user_notifications;
create policy "user_notifications_select_own"
  on public.user_notifications
  for select
  using (auth.uid() = user_id);

drop policy if exists "user_notifications_insert_own" on public.user_notifications;
create policy "user_notifications_insert_own"
  on public.user_notifications
  for insert
  with check (auth.uid() = user_id);

drop policy if exists "user_notifications_update_own" on public.user_notifications;
create policy "user_notifications_update_own"
  on public.user_notifications
  for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "user_notifications_delete_own" on public.user_notifications;
create policy "user_notifications_delete_own"
  on public.user_notifications
  for delete
  using (auth.uid() = user_id);
