-- ============================================================
-- Change Tracking: previous_value / new_value columns
-- audit_logs — backend API audit trail
-- ============================================================
-- Stores the before/after state of a changed resource so every
-- audit row is a self-contained change record.
-- Both columns are JSONB so structured diffs can be queried.
-- PII/PHA (emails, names, passwords) must NEVER appear in these
-- columns — callers are responsible for passing only safe fields
-- (role names, status strings, model IDs, UUIDs).
-- Both columns are included in the SHA-256 integrity_hash so any
-- post-write tampering is detectable.
-- ============================================================

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS previous_value JSONB;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS new_value JSONB;

-- Index: fast lookup of all changes to a specific resource
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_id
  ON public.audit_logs (resource_id)
  WHERE resource_id IS NOT NULL;
