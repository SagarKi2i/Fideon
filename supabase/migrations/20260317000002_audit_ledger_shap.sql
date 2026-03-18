-- ============================================================
-- Audit Ledger: Cryptographic Chain + SHAP AI Reasoning
-- ============================================================
-- Upgrades audit_logs to a full cryptographic ledger by adding:
--
--   sequence_num  — IDENTITY column: strict monotonic insert order
--   chain_hash    — SHA-256(prev_chain_hash ∥ integrity_hash)
--                   Each row binds to its predecessor, so inserting,
--                   removing, or reordering any row invalidates every
--                   chain_hash that follows it.
--
-- Adds AI explainability columns for SHAP-based reasoning:
--
--   shap_values   — JSONB: {feature_name: shap_float, ...}
--   model_id      — identifier of the model that produced the decision
--   prediction    — model output / decision outcome (JSONB)
--   reasoning     — auto-generated human-readable SHAP explanation
--
-- All five new fields are included in the per-row integrity_hash
-- (computed by the application layer in supabase.py) so tampering
-- with any field breaks both the row hash and the ledger chain.
--
-- Compliance: EU AI Act Art.12/13, SOC2 CC7.2, NAIC AI Bulletin
-- ============================================================

-- pgcrypto is required for the SHA-256 chain computation in the trigger.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── New columns ───────────────────────────────────────────────

-- sequence_num: monotonic insert order — never supplied by the caller.
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS sequence_num BIGINT GENERATED ALWAYS AS IDENTITY;

-- chain_hash: set exclusively by the trigger below, never by the caller.
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS chain_hash TEXT;

-- SHAP / AI explainability fields (nullable — only present on AI decisions).
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS shap_values JSONB;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS model_id TEXT;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS prediction JSONB;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS reasoning TEXT;

-- ── Indexes ───────────────────────────────────────────────────

-- Fast "latest block" lookup used by the chain trigger.
CREATE INDEX IF NOT EXISTS idx_audit_logs_sequence_num
  ON public.audit_logs (sequence_num DESC);

-- Filter AI-decision rows quickly (WHERE model_id IS NOT NULL).
CREATE INDEX IF NOT EXISTS idx_audit_logs_model_id
  ON public.audit_logs (model_id)
  WHERE model_id IS NOT NULL;

-- ── Chain Hash Trigger ────────────────────────────────────────
-- Fires BEFORE INSERT; overwrites chain_hash with the computed value.
-- Uses pg_advisory_xact_lock to serialise concurrent inserts, ensuring
-- the chain is always linear (no forks or ties between parallel writers).

CREATE OR REPLACE FUNCTION public.compute_audit_chain_hash()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  prev_chain_hash TEXT;
BEGIN
  -- Acquire a session-scoped advisory lock so concurrent inserts queue
  -- behind each other and always read the true latest chain_hash.
  PERFORM pg_advisory_xact_lock(hashtext('audit_ledger_chain'));

  SELECT chain_hash
    INTO prev_chain_hash
    FROM public.audit_logs
   ORDER BY sequence_num DESC
   LIMIT 1;

  -- Genesis block: no previous row exists yet.
  IF prev_chain_hash IS NULL THEN
    prev_chain_hash := 'GENESIS';
  END IF;

  -- chain_hash_N = SHA-256( chain_hash_{N-1} || integrity_hash_N )
  NEW.chain_hash := encode(
    digest(prev_chain_hash || COALESCE(NEW.integrity_hash, ''), 'sha256'),
    'hex'
  );

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS audit_logs_chain_hash ON public.audit_logs;
CREATE TRIGGER audit_logs_chain_hash
  BEFORE INSERT ON public.audit_logs
  FOR EACH ROW
  EXECUTE FUNCTION public.compute_audit_chain_hash();

-- ── Ledger Verification Function ─────────────────────────────
-- Walks the entire ledger in sequence order and re-derives every
-- chain_hash from scratch.  Rows where stored_chain ≠ computed_chain
-- indicate tampering (insertion, deletion, or modification).
--
-- Usage:
--   SELECT * FROM public.verify_audit_ledger() WHERE NOT is_valid;

CREATE OR REPLACE FUNCTION public.verify_audit_ledger()
RETURNS TABLE (
  sequence_num   BIGINT,
  id             UUID,
  stored_chain   TEXT,
  computed_chain TEXT,
  is_valid       BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  rec            RECORD;
  prev_chain     TEXT := 'GENESIS';
  expected_chain TEXT;
BEGIN
  FOR rec IN
    SELECT al.sequence_num, al.id, al.integrity_hash, al.chain_hash
      FROM public.audit_logs al
     ORDER BY al.sequence_num ASC
  LOOP
    expected_chain := encode(
      digest(prev_chain || COALESCE(rec.integrity_hash, ''), 'sha256'),
      'hex'
    );

    RETURN QUERY SELECT
      rec.sequence_num,
      rec.id,
      rec.chain_hash   AS stored_chain,
      expected_chain   AS computed_chain,
      (rec.chain_hash = expected_chain) AS is_valid;

    prev_chain := rec.chain_hash;
  END LOOP;
END;
$$;
