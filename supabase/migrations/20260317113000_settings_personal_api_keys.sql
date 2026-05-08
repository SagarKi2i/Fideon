-- Personal API keys for Settings page (profile/preferences/API keys).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.personal_api_keys (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name text NOT NULL CHECK (length(name) > 0 AND length(name) <= 80),
  key_prefix text NOT NULL CHECK (length(key_prefix) >= 8),
  key_hash_sha256 text NOT NULL UNIQUE CHECK (length(key_hash_sha256) = 64),
  key_prefix_sha256 text NOT NULL CHECK (length(key_prefix_sha256) >= 8),
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  last_used_at timestamptz NULL,
  revoked_at timestamptz NULL
);

CREATE INDEX IF NOT EXISTS idx_personal_api_keys_user_id
  ON public.personal_api_keys (user_id);

CREATE INDEX IF NOT EXISTS idx_personal_api_keys_created_at
  ON public.personal_api_keys (created_at DESC);

ALTER TABLE public.personal_api_keys ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own personal api keys" ON public.personal_api_keys;
CREATE POLICY "Users can view own personal api keys"
  ON public.personal_api_keys
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create own personal api keys" ON public.personal_api_keys;
CREATE POLICY "Users can create own personal api keys"
  ON public.personal_api_keys
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own personal api keys" ON public.personal_api_keys;
CREATE POLICY "Users can update own personal api keys"
  ON public.personal_api_keys
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
