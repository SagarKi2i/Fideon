-- =============================================================================
-- Phase 2: Local Training
-- Device-side LoRA fine-tuning jobs seeded from approved extraction samples.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- training_feedback
-- User corrections collected on-device; raw signal for local training.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.training_feedback (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

  device_id           TEXT        NOT NULL,
  model_id            TEXT        NOT NULL,

  original_response   TEXT        NOT NULL,
  corrected_response  TEXT        NOT NULL,

  rating              SMALLINT    CHECK (rating BETWEEN 1 AND 5),
  context_json        JSONB       NOT NULL DEFAULT '{}'::JSONB,

  used_in_training    BOOLEAN     NOT NULL DEFAULT false,
  training_job_id     UUID,                        -- FK set after job created

  tenant_id           UUID        REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tf_device_id       ON public.training_feedback(device_id);
CREATE INDEX IF NOT EXISTS idx_tf_model_id        ON public.training_feedback(model_id);
CREATE INDEX IF NOT EXISTS idx_tf_used            ON public.training_feedback(used_in_training);
CREATE INDEX IF NOT EXISTS idx_tf_created_at      ON public.training_feedback(created_at DESC);

-- ---------------------------------------------------------------------------
-- fl_local_training_jobs
-- One row per local training run on a device.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fl_local_training_jobs (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

  device_id        TEXT        NOT NULL,
  model_id         TEXT        NOT NULL,
  base_adapter_ver TEXT,                           -- adapter version trained on top of

  status           TEXT        NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','running','completed','failed','cancelled')),

  num_samples      INTEGER     NOT NULL DEFAULT 0,
  num_epochs       INTEGER     NOT NULL DEFAULT 3,
  learning_rate    FLOAT8      NOT NULL DEFAULT 2e-4,
  lora_rank        INTEGER     NOT NULL DEFAULT 8,

  train_loss       FLOAT8,
  val_loss         FLOAT8,
  perplexity       FLOAT8,

  adapter_path     TEXT,                           -- local path of output adapter
  error            TEXT,
  started_at       TIMESTAMPTZ,
  finished_at      TIMESTAMPTZ,

  metrics_json     JSONB       NOT NULL DEFAULT '{}'::JSONB,
  tenant_id        UUID        REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_fl_ltj_device_id   ON public.fl_local_training_jobs(device_id);
CREATE INDEX IF NOT EXISTS idx_fl_ltj_model_id    ON public.fl_local_training_jobs(model_id);
CREATE INDEX IF NOT EXISTS idx_fl_ltj_status      ON public.fl_local_training_jobs(status);
CREATE INDEX IF NOT EXISTS idx_fl_ltj_created_at  ON public.fl_local_training_jobs(created_at DESC);

DROP TRIGGER IF EXISTS trg_fl_ltj_updated_at ON public.fl_local_training_jobs;
CREATE TRIGGER trg_fl_ltj_updated_at
  BEFORE UPDATE ON public.fl_local_training_jobs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- Back-fill FK on training_feedback once jobs exist
ALTER TABLE public.training_feedback
  ADD CONSTRAINT IF NOT EXISTS fk_tf_training_job
  FOREIGN KEY (training_job_id)
  REFERENCES public.fl_local_training_jobs(id)
  ON DELETE SET NULL
  DEFERRABLE INITIALLY DEFERRED;

-- RLS: device rows are service-role only; no direct user access
ALTER TABLE public.training_feedback       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fl_local_training_jobs  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins manage training feedback"      ON public.training_feedback;
CREATE POLICY "Admins manage training feedback"
  ON public.training_feedback FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Admins manage local training jobs"    ON public.fl_local_training_jobs;
CREATE POLICY "Admins manage local training jobs"
  ON public.fl_local_training_jobs FOR ALL
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));
