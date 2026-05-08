-- WhatsApp-style short-lived pairing sessions for device linking.
CREATE TABLE IF NOT EXISTS public.device_pairings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  pairing_code_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'expired', 'cancelled')),
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ,
  linked_device_id UUID REFERENCES public.devices(id) ON DELETE SET NULL,
  primary_device_label TEXT,
  requested_device_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
  confirmed_device_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_device_pairings_user_status
  ON public.device_pairings(user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_device_pairings_expires_at
  ON public.device_pairings(expires_at);

ALTER TABLE public.device_pairings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own device pairings" ON public.device_pairings;
CREATE POLICY "Users can view own device pairings"
  ON public.device_pairings FOR SELECT
  USING (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Users can insert own device pairings" ON public.device_pairings;
CREATE POLICY "Users can insert own device pairings"
  ON public.device_pairings FOR INSERT
  WITH CHECK (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Users can update own pending pairings" ON public.device_pairings;
CREATE POLICY "Users can update own pending pairings"
  ON public.device_pairings FOR UPDATE
  USING (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'))
  WITH CHECK (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'));

DROP POLICY IF EXISTS "Admins can delete device pairings" ON public.device_pairings;
CREATE POLICY "Admins can delete device pairings"
  ON public.device_pairings FOR DELETE
  USING (public.has_role(auth.uid(), 'admin'));

DROP TRIGGER IF EXISTS update_device_pairings_updated_at ON public.device_pairings;
CREATE TRIGGER update_device_pairings_updated_at
  BEFORE UPDATE ON public.device_pairings
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();
