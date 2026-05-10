-- ─────────────────────────────────────────────────────────────────────────────
-- User Creation Requests
-- Approval workflow: admin→admin needs global_admin approval;
--                   user→user needs admin or global_admin approval.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.user_creation_requests (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  requested_by     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  requester_role   TEXT        NOT NULL CHECK (requester_role IN ('admin', 'user')),
  email            TEXT        NOT NULL,
  full_name        TEXT,
  requested_role   TEXT        NOT NULL CHECK (requested_role IN ('global_admin','admin','user','viewer','guest')),
  status           TEXT        NOT NULL DEFAULT 'pending'
                               CHECK (status IN ('pending', 'approved', 'rejected')),
  reviewed_by      UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
  rejection_reason TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at      TIMESTAMPTZ
);

-- Index for fast pending-request queries
CREATE INDEX IF NOT EXISTS ucr_status_idx ON public.user_creation_requests (status);
CREATE INDEX IF NOT EXISTS ucr_requested_by_idx ON public.user_creation_requests (requested_by);

-- ── Row-Level Security ────────────────────────────────────────────────────────
ALTER TABLE public.user_creation_requests ENABLE ROW LEVEL SECURITY;

-- Requesters can see their own requests
DROP POLICY IF EXISTS "ucr_requester_select" ON public.user_creation_requests;
CREATE POLICY "ucr_requester_select"
  ON public.user_creation_requests FOR SELECT
  USING (requested_by = auth.uid());

-- Admins (and global_admin via has_role hierarchy) can see all requests
DROP POLICY IF EXISTS "ucr_admin_select" ON public.user_creation_requests;
CREATE POLICY "ucr_admin_select"
  ON public.user_creation_requests FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'));

-- Any authenticated user whose role is 'admin' or 'user' can submit a request
DROP POLICY IF EXISTS "ucr_insert" ON public.user_creation_requests;
CREATE POLICY "ucr_insert"
  ON public.user_creation_requests FOR INSERT
  WITH CHECK (requested_by = auth.uid());

-- Only admins can update (approve / reject)
DROP POLICY IF EXISTS "ucr_admin_update" ON public.user_creation_requests;
CREATE POLICY "ucr_admin_update"
  ON public.user_creation_requests FOR UPDATE
  USING (public.has_role(auth.uid(), 'admin'));

-- Service role (backend) can delete if needed
DROP POLICY IF EXISTS "ucr_service_delete" ON public.user_creation_requests;
CREATE POLICY "ucr_service_delete"
  ON public.user_creation_requests FOR DELETE
  USING (true);
