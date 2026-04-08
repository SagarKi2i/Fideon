-- Model Registry: stores benchmark metrics per insurance task/model.
-- This table is read via backend admin endpoints (service role) and optionally
-- populated via MLflow sync.

create table if not exists public.model_registry (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid null,

  task_key text not null,
  task_label text not null,

  base_model text not null,
  display_name text null,

  bleu_score double precision null,
  f1_score double precision null,
  latency_ms double precision null,

  is_best_for_task boolean not null default false,

  mlflow_run_id text null,
  mlflow_experiment_id text null,
  source text not null default 'manual',

  metadata jsonb null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Common query patterns
create index if not exists model_registry_task_key_idx on public.model_registry (task_key);
create index if not exists model_registry_tenant_id_idx on public.model_registry (tenant_id);
create index if not exists model_registry_best_idx on public.model_registry (task_key, is_best_for_task);

-- MLflow sync uses run_id to upsert
create unique index if not exists model_registry_mlflow_run_id_uidx
  on public.model_registry (mlflow_run_id)
  where mlflow_run_id is not null;

-- Keep updated_at fresh on updates
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_model_registry_updated_at on public.model_registry;
create trigger set_model_registry_updated_at
before update on public.model_registry
for each row
execute function public.set_updated_at();

