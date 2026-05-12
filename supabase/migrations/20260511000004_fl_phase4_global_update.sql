-- =============================================================================
-- Phase 4: Global Update
-- FedAvg aggregation results and promoted global model versions.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- federated_aggregations
-- Audit record written after every successful FedAvg run.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.federated_aggregations (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  aggregated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

  round_id            UUID        NOT NULL REFERENCES public.federated_rounds(id) ON DELETE CASCADE,

  version             TEXT        NOT NULL,         -- e.g. "v12"
  num_contributions   INTEGER     NOT NULL DEFAULT 0,

  -- Azure Blob prefixes written by the aggregator
  adapter_prefix      TEXT        NOT NULL,         -- adapters/federated/v12/
  finetuned_prefix    TEXT        NOT NULL,         -- finetuned/v12/
  gguf_prefix         TEXT        NOT NULL DEFAULT '', -- gguf/federated/v12/  (empty = skipped)

  -- Quality gate
  avg_train_loss      FLOAT8,
  avg_val_loss        FLOAT8,
  passed_quality_gate BOOLEAN     NOT NULL DEFAULT false,

  algorithm           TEXT        NOT NULL DEFAULT 'fedavg',
  metadata_json       JSONB       NOT NULL DEFAULT '{}'::JSONB
);

CREATE INDEX IF NOT EXISTS idx_fl_agg_round_id      ON public.federated_aggregations(round_id);
CREATE INDEX IF NOT EXISTS idx_fl_agg_version       ON public.federated_aggregations(version);
CREATE INDEX IF NOT EXISTS idx_fl_agg_aggregated_at ON public.federated_aggregations(aggregated_at DESC);

-- One aggregation per round
CREATE UNIQUE INDEX IF NOT EXISTS idx_fl_agg_round_unique
  ON public.federated_aggregations(round_id);

-- ---------------------------------------------------------------------------
-- global_model_versions
-- Canonical registry of every promoted global model.
-- Devices poll this to discover new adapter downloads.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.global_model_versions (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

  model_id         TEXT        NOT NULL,
  version          TEXT        NOT NULL,            -- e.g. "v12"
  version_num      INTEGER     NOT NULL,            -- numeric for easy ordering

  source           TEXT        NOT NULL DEFAULT 'federated'
    CHECK (source IN ('federated','supervised','manual')),

  aggregation_id   UUID        REFERENCES public.federated_aggregations(id) ON DELETE SET NULL,

  -- Azure Blob locations
  adapter_prefix   TEXT        NOT NULL,
  finetuned_prefix TEXT        NOT NULL,
  gguf_prefix      TEXT        NOT NULL DEFAULT '',

  -- Rollout control
  is_active        BOOLEAN     NOT NULL DEFAULT false,
  canary_pct       INTEGER     NOT NULL DEFAULT 0
    CHECK (canary_pct BETWEEN 0 AND 100),
  promoted_at      TIMESTAMPTZ,
  promoted_by      UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
  rolled_back_at   TIMESTAMPTZ,

  -- Quality
  avg_train_loss   FLOAT8,
  avg_val_loss     FLOAT8,
  num_contributors INTEGER     NOT NULL DEFAULT 0,

  release_notes    TEXT,
  metadata_json    JSONB       NOT NULL DEFAULT '{}'::JSONB,

  UNIQUE (model_id, version)
);

CREATE INDEX IF NOT EXISTS idx_gmv_model_id    ON public.global_model_versions(model_id);
CREATE INDEX IF NOT EXISTS idx_gmv_is_active   ON public.global_model_versions(model_id, is_active);
CREATE INDEX IF NOT EXISTS idx_gmv_version_num ON public.global_model_versions(model_id, version_num DESC);
CREATE INDEX IF NOT EXISTS idx_gmv_created_at  ON public.global_model_versions(created_at DESC);

-- ---------------------------------------------------------------------------
-- RPC: promote_global_version(p_model_id, p_version)
-- Atomically deactivates the current version and activates the new one.
-- Called by the aggregator after quality gate passes.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.promote_global_version(
  p_model_id TEXT,
  p_version  TEXT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- Deactivate current active version
  UPDATE public.global_model_versions
  SET is_active = false,
      canary_pct = 0
  WHERE model_id = p_model_id
    AND is_active = true;

  -- Activate target version
  UPDATE public.global_model_versions
  SET is_active    = true,
      canary_pct   = 100,
      promoted_at  = now()
  WHERE model_id = p_model_id
    AND version   = p_version;
END;
$$;

-- RLS
ALTER TABLE public.federated_aggregations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.global_model_versions   ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins manage federated aggregations" ON public.federated_aggregations;
CREATE POLICY "Admins manage federated aggregations"
  ON public.federated_aggregations FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Anyone can read active global versions" ON public.global_model_versions;
CREATE POLICY "Anyone can read active global versions"
  ON public.global_model_versions FOR SELECT
  USING (is_active = true);

DROP POLICY IF EXISTS "Admins manage global model versions" ON public.global_model_versions;
CREATE POLICY "Admins manage global model versions"
  ON public.global_model_versions FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
