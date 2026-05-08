-- ============================================================
-- Immutable Audit Log Enforcement
-- EU AI Act (Art. 12/13), SOC2 (CC7.2/CC9.1), NAIC AI Bulletin
-- ============================================================
-- Audit rows must be append-only. No UPDATE or DELETE is ever
-- permitted — not by users, not by admins, not by service_role.
-- Triggers fire before the operation regardless of RLS bypass.
-- Only a Postgres superuser running ALTER TABLE ... DISABLE TRIGGER
-- can circumvent this, and that action itself is logged by Postgres.
-- ============================================================

-- Shared trigger function: raises an exception on any modification attempt.
CREATE OR REPLACE FUNCTION public.prevent_audit_modification()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RAISE EXCEPTION
    'Audit log records are immutable (EU AI Act Art.12 / SOC2 CC7.2 / NAIC). '
    'Operation "%" on table "%" is not permitted.',
    TG_OP, TG_TABLE_NAME;
END;
$$;

-- ── auth_audit ───────────────────────────────────────────────
DROP TRIGGER IF EXISTS auth_audit_no_update ON public.auth_audit;
CREATE TRIGGER auth_audit_no_update
  BEFORE UPDATE ON public.auth_audit
  FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_modification();

DROP TRIGGER IF EXISTS auth_audit_no_delete ON public.auth_audit;
CREATE TRIGGER auth_audit_no_delete
  BEFORE DELETE ON public.auth_audit
  FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_modification();

-- ── audit_logs ───────────────────────────────────────────────
DROP TRIGGER IF EXISTS audit_logs_no_update ON public.audit_logs;
CREATE TRIGGER audit_logs_no_update
  BEFORE UPDATE ON public.audit_logs
  FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_modification();

DROP TRIGGER IF EXISTS audit_logs_no_delete ON public.audit_logs;
CREATE TRIGGER audit_logs_no_delete
  BEFORE DELETE ON public.audit_logs
  FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_modification();

-- ── Add integrity_hash to audit_logs ─────────────────────────
-- auth_audit already has this column. audit_logs was missing it.
-- Hash is computed by the caller over: user_id, action,
-- resource_type, resource_id, created_at (non-PII fields).
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS integrity_hash TEXT;

-- ── Retention comment (operational requirement) ──────────────
-- EU AI Act requires logs retained ≥ 6 months for deployers.
-- SOC2 / NAIC typically require ≥ 12 months.
-- Implement via pg_cron archival to cold storage — DO NOT DELETE.
-- Example (run separately after enabling pg_cron extension):
--
--   SELECT cron.schedule(
--     'archive-old-audit-logs',
--     '0 2 * * 0',   -- every Sunday at 02:00 UTC
--     $$
--       INSERT INTO public.audit_logs_archive SELECT * FROM public.audit_logs
--         WHERE created_at < now() - interval '13 months';
--       -- Note: DELETE from live table requires disabling trigger temporarily
--       -- under a controlled, logged superuser session only.
--     $$
--   );
