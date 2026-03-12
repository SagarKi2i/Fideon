# Next.js + FastAPI Conversion

This folder contains the converted stack from the original Electron/Vite + Supabase Edge Functions project.

## Structure

- `frontend/` - Next.js frontend (migrated UI and routing logic)
- `backend/` - FastAPI backend (replaces Supabase Edge Functions)

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

## Important

- All backend runtime functions are served by FastAPI (`backend/`).
- The frontend calls FastAPI (`NEXT_PUBLIC_API_URL`) and does not call Supabase Edge Functions.
- `supabase/` now keeps database migration assets only (no Edge Function runtime files).
- Current implementation still uses Supabase Auth tokens for user/session verification.
