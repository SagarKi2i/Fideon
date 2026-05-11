-- =============================================================================
-- Phase 3: Share Gradients
-- Federated rounds coordination and per-device adapter uploads (gradients).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- federated_rounds
-- Server-created round that devices contribute to.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.federated_rounds (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

  model_id            TEXT        NOT NULL,
  round_number        INTEGER     NOT NULL,

  status              TEXT        NOT NULL DEFAULT 'collecting'
    CHECK (status IN ('collecting','aggregating','completed','failed')),

  min_participants    INTEGER     NOT NULL DEFAULT 3,
  current_participants INTEGER    NOT NULL DEFAULT 0,

  deadline            TIMESTAMPTZ,
  aggregated_version  TEXT,                        -- e.g. "v12", set after FedAvg
  error               TEXT,

  started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at           TIMESTAMPTZ,

  config_json         JSONB       NOT NULL DEFAULT '{}'::JSONB,
  tenant_id           UUID        REFERENCES auth.users(id) ON DELETE SET NULL,

  UNIQUE (model_id, round_number)
);

CREATE INDEX IF NOT EXISTS idx_fl_rounds_model_id    ON public.federated_rounds(model_id);
CREATE INDEX IF NOT EXISTS idx_fl_rounds_status      ON public.federated_rounds(status);
CREATE INDEX IF NOT EXISTS idx_fl_rounds_created_at  ON public.federated_rounds(created_at DESC);

DROP TRIGGER IF EXISTS trg_fl_rounds_updated_at ON public.federated_rounds;
CREATE TRIGGER trg_fl_rounds_updated_at
  BEFORE UPDATE ON public.federated_rounds
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- federated_updates
-- One row per device submission within a round (the "gradient upload").
-- storage_path points to the LoRA adapter in SeaweedFS:
--   gradients/{model_id}/round-{N}/{device_id}/
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.federated_updates (
  id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

  round_id              UUID        NOT NULL REFERENCES public.federated_rounds(id) ON DELETE CASCADE,
  model_id              TEXT        NOT NULL,
  round_number          INTEGER     NOT NULL,
  device_id             TEXT        NOT NULL,

  storage_path          TEXT        NOT NULL,       -- SeaweedFS prefix
  gradient_hash         TEXT        NOT NULL,       -- SHA-256 of adapter bytes
  gradient_size_bytes   BIGINT      NOT NULL DEFAULT 0,

  privacy_noise_added   BOOLEAN     NOT NULL DEFAULT false,
  dp_epsilon            FLOAT8,                     -- differential privacy budget used

  training_job_id       UUID        REFERENCES public.fl_local_training_jobs(id) ON DELETE SET NULL,

  metrics               JSONB       NOT NULL DEFAULT '{}'::JSONB,
  -- e.g. {"train_loss": 0.32, "val_loss": 0.41, "num_samples": 120}

  UNIQUE (round_id, device_id)                      -- one submission per device per round
);

CREATE INDEX IF NOT EXISTS idx_fl_updates_round_id    ON public.federated_updates(round_id);
CREATE INDEX IF NOT EXISTS idx_fl_updates_device_id   ON public.federated_updates(device_id);
CREATE INDEX IF NOT EXISTS idx_fl_updates_model_id    ON public.federated_updates(model_id);
CREATE INDEX IF NOT EXISTS idx_fl_updates_created_at  ON public.federated_updates(created_at DESC);

-- RLS: backend uses service role; no direct user reads
ALTER TABLE public.federated_rounds  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.federated_updates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins manage federated rounds"   ON public.federated_rounds;
CREATE POLICY "Admins manage federated rounds"
  ON public.federated_rounds FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Admins manage federated updates"  ON public.federated_updates;
CREATE POLICY "Admins manage federated updates"
  ON public.federated_updates FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
