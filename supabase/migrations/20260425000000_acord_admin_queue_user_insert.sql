-- Allow users to submit their own runs for admin review.
-- The existing policy only grants admins full access; this adds a targeted
-- INSERT right so the frontend can call sendAcordToReview() directly without
-- routing through the backend service role.

DROP POLICY IF EXISTS "Users can request review for own runs" ON public.acord_admin_queue;
CREATE POLICY "Users can request review for own runs"
  ON public.acord_admin_queue
  FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.acord_extraction_runs r
      WHERE r.id = run_id AND r.created_by = auth.uid()
    )
  );
