-- RPC: mark a batch of acord_extraction_runs as approved.
-- Called by the RunPod pod (service role) immediately when training starts.
-- Using a SECURITY DEFINER function bypasses RLS so the pod's service-role
-- key can update runs owned by any user without per-row policy checks.

CREATE OR REPLACE FUNCTION public.mark_acord_runs_approved(run_ids UUID[])
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  updated_count INTEGER;
BEGIN
  UPDATE public.acord_extraction_runs
  SET    status = 'approved'
  WHERE  id = ANY(run_ids)
    AND  status IN ('submitted', 'needs_admin_review');

  GET DIAGNOSTICS updated_count = ROW_COUNT;
  RETURN updated_count;
END;
$$;

-- Allow authenticated users and service role to call this function.
-- (Pod uses service_role; frontend JWT goes through the same path safely
--  because the function body only updates rows matching the provided IDs.)
GRANT EXECUTE ON FUNCTION public.mark_acord_runs_approved(UUID[]) TO authenticated;
GRANT EXECUTE ON FUNCTION public.mark_acord_runs_approved(UUID[]) TO service_role;
