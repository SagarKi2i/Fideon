
-- Training feedback collected from users on AI outputs
CREATE TABLE public.training_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid REFERENCES public.devices(id) ON DELETE CASCADE NOT NULL,
  model_id text NOT NULL,
  prompt text NOT NULL,
  original_response text NOT NULL,
  corrected_response text,
  rating integer CHECK (rating >= 1 AND rating <= 5),
  feedback_type text NOT NULL DEFAULT 'correction', -- correction, rating, thumbs
  metadata jsonb DEFAULT '{}'::jsonb,
  is_used_for_training boolean DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.training_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Device functions can insert feedback"
  ON public.training_feedback FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Admins can view all feedback"
  ON public.training_feedback FOR SELECT
  USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can update feedback"
  ON public.training_feedback FOR UPDATE
  USING (has_role(auth.uid(), 'admin'::app_role));

-- Local training jobs run on devices
CREATE TABLE public.training_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid REFERENCES public.devices(id) ON DELETE CASCADE NOT NULL,
  model_id text NOT NULL,
  status text NOT NULL DEFAULT 'pending', -- pending, running, completed, failed
  training_type text NOT NULL DEFAULT 'lora', -- lora, modelfile, full
  config jsonb DEFAULT '{}'::jsonb,
  metrics jsonb DEFAULT '{}'::jsonb, -- loss, accuracy, epochs
  feedback_count integer DEFAULT 0,
  started_at timestamptz,
  completed_at timestamptz,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.training_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Device functions can manage training jobs"
  ON public.training_jobs FOR ALL
  USING (true);

CREATE POLICY "Admins can view all training jobs"
  ON public.training_jobs FOR SELECT
  USING (has_role(auth.uid(), 'admin'::app_role));

-- Federated model updates (gradient deltas from devices)
CREATE TABLE public.federated_updates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid REFERENCES public.devices(id) ON DELETE CASCADE NOT NULL,
  model_id text NOT NULL,
  round_number integer NOT NULL DEFAULT 1,
  gradient_hash text NOT NULL, -- hash of gradient delta for integrity
  gradient_size_bytes bigint DEFAULT 0,
  storage_path text, -- path in storage bucket
  metrics jsonb DEFAULT '{}'::jsonb, -- local training metrics
  status text NOT NULL DEFAULT 'pending', -- pending, accepted, rejected, aggregated
  privacy_noise_added boolean DEFAULT true,
  submitted_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.federated_updates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Device functions can insert updates"
  ON public.federated_updates FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Admins can manage federated updates"
  ON public.federated_updates FOR ALL
  USING (has_role(auth.uid(), 'admin'::app_role));

-- Federated rounds tracking
CREATE TABLE public.federated_rounds (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id text NOT NULL,
  round_number integer NOT NULL,
  status text NOT NULL DEFAULT 'collecting', -- collecting, aggregating, completed, distributed
  min_participants integer DEFAULT 3,
  current_participants integer DEFAULT 0,
  aggregated_model_path text,
  aggregation_method text DEFAULT 'fedavg', -- fedavg, fedprox, scaffold
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  distributed_at timestamptz,
  metrics jsonb DEFAULT '{}'::jsonb
);

ALTER TABLE public.federated_rounds ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage rounds"
  ON public.federated_rounds FOR ALL
  USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Devices can view active rounds"
  ON public.federated_rounds FOR SELECT
  USING (true);

-- Storage bucket for gradient deltas
INSERT INTO storage.buckets (id, name, public) VALUES ('model-updates', 'model-updates', false);

CREATE POLICY "Devices can upload gradients"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'model-updates');

CREATE POLICY "Admins can view gradients"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'model-updates' AND has_role(auth.uid(), 'admin'::app_role));
