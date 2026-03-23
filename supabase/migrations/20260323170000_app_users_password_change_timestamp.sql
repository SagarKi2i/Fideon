-- Track when a user last changed their password.
-- Keeps both a first-class timestamp column and compatibility metadata key.

ALTER TABLE public.app_users
  ADD COLUMN IF NOT EXISTS last_password_changed_at TIMESTAMPTZ;

-- Backfill from metadata key where available and parseable.
UPDATE public.app_users
SET last_password_changed_at = (metadata ->> 'password_updated_at')::timestamptz
WHERE last_password_changed_at IS NULL
  AND metadata ? 'password_updated_at'
  AND (metadata ->> 'password_updated_at') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T';

CREATE INDEX IF NOT EXISTS idx_app_users_last_password_changed_at
  ON public.app_users(last_password_changed_at DESC);
