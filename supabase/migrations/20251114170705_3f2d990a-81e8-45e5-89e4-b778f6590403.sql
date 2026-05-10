-- Fix search_path for generate_device_token function
CREATE OR REPLACE FUNCTION public.generate_device_token()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  token TEXT;
BEGIN
  token := encode(gen_random_bytes(32), 'base64');
  token := replace(token, '/', '_');
  token := replace(token, '+', '-');
  RETURN token;
END;
$$;