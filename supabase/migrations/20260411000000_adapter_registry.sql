-- Adapter registry: tracks quantized GGUF model artifacts available for
-- download by Electron devices. Populated by the quantization pipeline
-- (upload.py) and queried by the backend adapter_registry endpoints.

create table if not exists public.adapter_registry (
  id               uuid        primary key default gen_random_uuid(),

  -- Identity
  domain           text        not null,          -- e.g. "broker"
  adapter_version  text        not null,          -- e.g. "1.2.0"
  filename         text        not null,          -- e.g. "model-q5_k_m.gguf"
  quant_level      text        not null,          -- e.g. "q5_k_m"

  -- Integrity
  sha256           text        not null,          -- "sha256:<hex>"
  size_bytes       bigint      not null,

  -- Storage — object key in SeaweedFS bucket (NOT a presigned URL)
  blob_key         text        not null,          -- e.g. "broker/v1.2.0/model-q5_k_m.gguf"

  -- Electron compatibility
  min_electron_ver text        not null default '0.0.0',

  -- Canary rollout
  canary_pct       integer     not null default 100
                               check (canary_pct >= 0 and canary_pct <= 100),
  rollback_safe    boolean     not null default true,

  -- Availability
  is_available     boolean     not null default true,
  blocked          boolean     not null default false,

  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

-- Query patterns used by backend
create index if not exists adapter_registry_domain_version_idx
  on public.adapter_registry (domain, adapter_version desc);

create index if not exists adapter_registry_available_idx
  on public.adapter_registry (domain, is_available, blocked);

-- Prevent duplicate artifact registrations for the same version+quant
create unique index if not exists adapter_registry_version_quant_uidx
  on public.adapter_registry (domain, adapter_version, quant_level);

-- Keep updated_at current (reuse trigger function created by model_registry migration)
drop trigger if exists set_adapter_registry_updated_at on public.adapter_registry;
create trigger set_adapter_registry_updated_at
  before update on public.adapter_registry
  for each row
  execute function public.set_updated_at();

-- RLS: backend uses service role — no row-level security needed.
-- Devices never query this table directly; they go through the backend API.
alter table public.adapter_registry enable row level security;
