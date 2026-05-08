# Next.js + FastAPI Conversion

This folder contains the converted stack from the original Electron/Vite + Supabase Edge Functions project.

## Structure

- `frontend/` - Next.js frontend (migrated UI and routing logic)
- `backend/` - FastAPI backend (replaces Supabase Edge Functions)
- `supabase/` - Database migrations (schema, RLS, auth role/profile automation)

## 0) Database migration order (run first)

From `next-fastapi-conversion/` root:

1. Link Supabase project:
   - `npx supabase@latest link --project-ref <YOUR_PROJECT_REF> --workdir .`
2. Push all migrations:
   - `npx supabase@latest db push --workdir .`

This now includes Sprint-1 closure migrations for:
- `public.app_users`, `public.roles`, `public.tenants`, `public.model_catalog`
- RLS hardening for users/roles/audit/devices
- automatic role/profile rows for new `auth.users`

## Backend setup

1. Copy `backend/.env.example` to `backend/.env` and fill values.
2. Install dependencies:
   - `python -m pip install -r requirements.txt`
3. Run backend:
   - `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`

## Frontend setup

1. Copy `frontend/.env.example` to `frontend/.env.local` and fill values.
2. Install dependencies:
   - `npm install`
3. Run frontend:
   - `npm run dev`
4. Build frontend:

   - `npm run build`

## Auth provider toggles (frontend)

Configure these in `frontend/.env.local`:

- `NEXT_PUBLIC_AUTH_ENABLE_SSO=true|false`
- `NEXT_PUBLIC_AUTH_SSO_PROVIDERS=google,github,azure`
- `NEXT_PUBLIC_AUTH_ENABLE_MFA=true|false`

Email auth is fully enabled by default (sign-in, forgot password, reset password).
SSO and MFA are scaffolded and controlled via these flags plus Supabase dashboard provider setup.

## QA / smoke test commands

From `frontend/`:

- `npm run lint`
- `npm run test:run`
- `npm run build`

Manual checklist:
- `frontend/tests/SPRINT1_QA_CHECKLIST.md`

## Important

- All backend runtime functions are served by FastAPI (`backend/`).
- The frontend calls FastAPI (`NEXT_PUBLIC_API_URL`) and does not call Supabase Edge Functions.
- `supabase/` now keeps database migration assets only (no Edge Function runtime files).
- Current implementation still uses Supabase Auth tokens for user/session verification.
- CI/CD (`FNF-14`) is intentionally excluded in this Sprint-1 closure.
