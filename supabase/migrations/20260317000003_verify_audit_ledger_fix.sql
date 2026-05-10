-- ============================================================
-- Fix: verify_audit_ledger() — pre-migration NULL chain rows
-- ============================================================
-- Rows that existed before migration 20260317000002 have
-- chain_hash = NULL because the trigger had not yet been
-- created.  The original function propagated NULL into
-- prev_chain, causing NULL || integrity_hash = NULL in
-- PostgreSQL string concatenation, which silently broke
-- chain verification for every row that followed.
--
-- Fix: when chain_hash IS NULL, emit the row as a
-- "pre-migration" sentinel (is_valid = NULL) and do NOT
-- advance prev_chain, keeping it at 'GENESIS' until the
-- first post-migration row establishes the chain.
--
-- This is safe because:
--   • The trigger uses the same GENESIS seed for the first
--     post-migration insert (any existing row it reads has
--     chain_hash = NULL, so the IF IS NULL guard fires).
--   • Subsequent post-migration rows chain correctly from
--     the first post-migration chain_hash onward.
-- ============================================================

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
    -- Pre-migration rows have chain_hash = NULL.
    -- Report them as sentinel entries and keep prev_chain unchanged
    -- so the first post-migration row still verifies against GENESIS.
    IF rec.chain_hash IS NULL THEN
      RETURN QUERY SELECT
        rec.sequence_num,
        rec.id,
        NULL::TEXT  AS stored_chain,
        NULL::TEXT  AS computed_chain,
        NULL::BOOLEAN AS is_valid;
      CONTINUE;  -- do NOT update prev_chain
    END IF;

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
