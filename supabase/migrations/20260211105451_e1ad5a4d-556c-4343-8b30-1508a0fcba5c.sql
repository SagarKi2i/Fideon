-- Allow admins to view all activated models
CREATE POLICY "Admins can view all activated models"
ON public.activated_models
FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

-- Allow admins to insert activated models for any user
CREATE POLICY "Admins can allocate models to users"
ON public.activated_models
FOR INSERT
WITH CHECK (has_role(auth.uid(), 'admin'::app_role));

-- Allow admins to delete activated models for any user
CREATE POLICY "Admins can deallocate models from users"
ON public.activated_models
FOR DELETE
USING (has_role(auth.uid(), 'admin'::app_role));