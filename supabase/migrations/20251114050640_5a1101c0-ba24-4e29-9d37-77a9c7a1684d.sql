-- Fix function search path security issue by recreating triggers
DROP TRIGGER IF EXISTS update_model_endpoints_updated_at ON public.model_endpoints;
DROP TRIGGER IF EXISTS update_chat_conversations_updated_at ON public.chat_conversations;
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Recreate function with proper search_path
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public;

-- Recreate triggers
CREATE TRIGGER update_model_endpoints_updated_at
  BEFORE UPDATE ON public.model_endpoints
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_conversations_updated_at
  BEFORE UPDATE ON public.chat_conversations
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();