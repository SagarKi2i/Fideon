-- Domain and Agent catalog for RAG-aware agents

create table if not exists public.domain_catalog (
  id text primary key,
  display_name text not null,
  description text,
  rag_collection text,
  default_model_adapter text,
  data_path text,
  is_active boolean not null default true
);

create table if not exists public.agent_catalog (
  id text primary key,
  display_name text not null,
  domain_id text not null references public.domain_catalog(id) on delete cascade,
  category text,
  description text,
  system_prompt text,
  output_schema jsonb,
  rag_collection_override text,
  model_adapter_override text,
  tools jsonb,
  is_active boolean not null default true
);

