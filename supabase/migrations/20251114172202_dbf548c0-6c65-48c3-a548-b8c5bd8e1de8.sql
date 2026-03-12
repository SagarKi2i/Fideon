-- Fix generate_device_token to work with restricted search_path by qualifying pgcrypto function
CREATE OR REPLACE FUNCTION public.generate_device_token()
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  token TEXT;
BEGIN
  -- Use the pgcrypto function from the extensions schema explicitly
  token := encode(extensions.gen_random_bytes(32), 'base64');
  token := replace(token, '/', '_');
  token := replace(token, '+', '-');
  RETURN token;
END;
$$;