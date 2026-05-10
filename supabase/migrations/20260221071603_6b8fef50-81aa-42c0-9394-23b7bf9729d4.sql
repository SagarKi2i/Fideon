
-- Decision Review Queue table for human-in-the-loop across all pods
CREATE TABLE public.decision_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  pod_model_id text NOT NULL,
  pod_model_name text NOT NULL,
  domain text NOT NULL,
  decision_type text NOT NULL, -- e.g. 'quote_approval', 'claim_decision', 'submission_triage'
  title text NOT NULL,
  summary text,
  ai_recommendation text,
  confidence_score numeric,
  threshold_exceeded boolean DEFAULT true,
  input_data jsonb DEFAULT '{}'::jsonb,
  output_data jsonb DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending', -- pending, approved, rejected
  reviewer_id uuid,
  reviewer_notes text,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.decision_reviews ENABLE ROW LEVEL SECURITY;

-- Users can view their own decisions
CREATE POLICY "Users can view their own reviews"
ON public.decision_reviews FOR SELECT
USING (auth.uid() = user_id);

-- Users can create review requests
CREATE POLICY "Users can create reviews"
ON public.decision_reviews FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- Admins can view all reviews
CREATE POLICY "Admins can view all reviews"
ON public.decision_reviews FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

-- Admins can update reviews (approve/reject)
CREATE POLICY "Admins can update reviews"
ON public.decision_reviews FOR UPDATE
USING (has_role(auth.uid(), 'admin'::app_role));

-- Users can update their own pending reviews (e.g. cancel)
CREATE POLICY "Users can update own pending reviews"
ON public.decision_reviews FOR UPDATE
USING (auth.uid() = user_id AND status = 'pending');

-- Trigger for updated_at
CREATE TRIGGER update_decision_reviews_updated_at
BEFORE UPDATE ON public.decision_reviews
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();
