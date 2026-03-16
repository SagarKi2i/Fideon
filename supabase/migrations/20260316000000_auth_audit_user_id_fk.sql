-- Add foreign key constraint from auth_audit.user_id to auth.users(id)
-- This enforces referential integrity: audit rows cannot exist for deleted users.

alter table public.auth_audit
  add constraint auth_audit_user_id_fkey
  foreign key (user_id) references auth.users(id) on delete cascade;
