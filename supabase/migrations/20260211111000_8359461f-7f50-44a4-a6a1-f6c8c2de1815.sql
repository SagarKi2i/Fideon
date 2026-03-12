
-- Create pod activation requests table
CREATE TABLE public.pod_activation_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  model_id text NOT NULL,
  model_name text NOT NULL,
  domain text NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  requested_at timestamp with time zone NOT NULL DEFAULT now(),
  reviewed_at timestamp with time zone,
  reviewed_by uuid,
  rejection_reason text,
  UNIQUE(user_id, model_id, status)
);

-- Enable RLS
ALTER TABLE public.pod_activation_requests ENABLE ROW LEVEL SECURITY;

-- Users can create requests
CREATE POLICY "Users can create activation requests"
ON public.pod_activation_requests FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- Users can view their own requests
CREATE POLICY "Users can view their own requests"
ON public.pod_activation_requests FOR SELECT
USING (auth.uid() = user_id);

-- Admins can view all requests
CREATE POLICY "Admins can view all requests"
ON public.pod_activation_requests FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

-- Admins can update requests (approve/reject)
CREATE POLICY "Admins can update requests"
ON public.pod_activation_requests FOR UPDATE
USING (has_role(auth.uid(), 'admin'::app_role));

-- Users can delete their own pending requests
CREATE POLICY "Users can cancel pending requests"
ON public.pod_activation_requests FOR DELETE
USING (auth.uid() = user_id AND status = 'pending');
