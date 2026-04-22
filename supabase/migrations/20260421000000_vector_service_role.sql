-- =============================================================================
-- C2 · vector_service Postgres role scoped to rag_chunks only
--
-- Creates a dedicated low-privilege role for pgvector operations.
-- This role can ONLY read/write rag_chunks — it cannot touch any other table.
--
-- After running this migration:
--   1. Create a Postgres user for this role in Supabase dashboard (or via CLI):
--        CREATE USER vector_svc WITH PASSWORD '<strong-password>';
--        GRANT vector_service TO vector_svc;
--   2. Set PGVECTOR_DATABASE_URL to use vector_svc credentials instead of
--      the superuser/pooler credentials.
--   3. Rotate the old PGVECTOR_DATABASE_URL secret.
-- =============================================================================

-- Step 1: Create the restricted role (idempotent).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vector_service') THEN
        CREATE ROLE vector_service NOLOGIN;
    END IF;
END
$$;

-- Step 2: Grant schema access.
GRANT USAGE ON SCHEMA public TO vector_service;

-- Step 3: Grant table access — rag_chunks ONLY.
-- SELECT + INSERT + UPDATE are needed for upsert_chunks() and query_similar().
-- DELETE is intentionally NOT granted — chunks are append/update only.
GRANT SELECT, INSERT, UPDATE ON TABLE public.rag_chunks TO vector_service;

-- Step 4: Revoke all other table access to enforce least privilege.
-- This ensures that even if the role is misconfigured, it cannot read
-- app_users, devices, documents, audit_logs, or any other tenant table.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM vector_service;
GRANT SELECT, INSERT, UPDATE ON TABLE public.rag_chunks TO vector_service;

-- Step 5: Allow the role to use sequences (needed for generated IDs, if any).
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO vector_service;

-- Step 6: Add tenant_id column to rag_chunks if not already present
-- (also handled in pgvector_store.py ensure_schema(), but explicit here for
--  environments where the Python migration path is not run first).
ALTER TABLE public.rag_chunks
    ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Step 7: Add tenant + collection composite index for scoped similarity searches.
CREATE INDEX IF NOT EXISTS rag_chunks_tenant_collection_idx
    ON public.rag_chunks (tenant_id, collection_name);

-- Step 8: Row-level policy — vector_service role can only see its own tenant's rows.
-- NOTE: RLS on rag_chunks requires the calling session to SET app.tenant_id
--       before running queries. The pgvector_store.py layer enforces this via
--       the tenant_id parameter in query_similar() / upsert_chunks().
--       This RLS policy is an additional DB-layer safety net.
ALTER TABLE public.rag_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rag_chunks_tenant_isolation ON public.rag_chunks;
CREATE POLICY rag_chunks_tenant_isolation
    ON public.rag_chunks
    FOR ALL
    TO vector_service
    USING (
        tenant_id = current_setting('app.tenant_id', true)
        OR tenant_id IS NULL  -- shared/catalog chunks visible to all tenants
    );

-- Superuser and service_role bypass RLS (Supabase default behaviour).
-- This migration does not change that.

COMMENT ON ROLE vector_service IS
    'Restricted role for pgvector/RAG operations. '
    'Scoped to rag_chunks table only. '
    'Use with PGVECTOR_DATABASE_URL — never use service_role credentials for vector ops.';
