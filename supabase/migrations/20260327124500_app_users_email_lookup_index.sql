-- Speed up email availability checks during signup.
-- Query pattern: select ... from app_users where lower(email)=lower(:email) limit 1

CREATE INDEX IF NOT EXISTS idx_app_users_email_lower
  ON public.app_users ((lower(email)));

-- Also keep a direct index for exact comparisons if callers already normalize.
CREATE INDEX IF NOT EXISTS idx_app_users_email
  ON public.app_users (email);
