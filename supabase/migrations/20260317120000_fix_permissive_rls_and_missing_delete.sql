-- Fix 1: personal_api_keys missing DELETE policy
DROP POLICY IF EXISTS "Users can delete own personal api keys" ON public.personal_api_keys;
CREATE POLICY "Users can delete own personal api keys"
  ON public.personal_api_keys
  FOR DELETE
  USING (auth.uid() = user_id);

-- Fix 2: training_jobs had USING (true) FOR ALL — any user could read/modify any job
DROP POLICY IF EXISTS "Device functions can manage training jobs" ON public.training_jobs;

-- Only admins can manage training jobs directly (device firmware uses service_role)
DROP POLICY IF EXISTS "Admins can manage training jobs" ON public.training_jobs;
CREATE POLICY "Admins can manage training jobs"
  ON public.training_jobs FOR ALL
  USING (public.has_role(auth.uid(), 'admin'::public.app_role))
  WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

-- Fix 3: federated_updates INSERT had WITH CHECK (true) — any user could insert for any device
DROP POLICY IF EXISTS "Device functions can insert updates" ON public.federated_updates;

-- Only admins can insert federated updates directly (devices use service_role)
DROP POLICY IF EXISTS "Admins can insert federated updates" ON public.federated_updates;
CREATE POLICY "Admins can insert federated updates"
  ON public.federated_updates FOR INSERT
  WITH CHECK (public.has_role(auth.uid(), 'admin'::public.app_role));

-- Fix 4: user_roles tenant-JOIN policy caused 500 errors on every role lookup
-- The JOIN to app_users inside an RLS policy creates a cascading evaluation crash
DROP POLICY IF EXISTS "Admins can view user roles in own tenant" ON public.user_roles;
CREATE POLICY "Admins can view all user roles"
  ON public.user_roles
  FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'::public.app_role));
