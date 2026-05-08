-- Expand role enum values first in isolated migration.

ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'global_admin';
ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'viewer';
ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'guest';
