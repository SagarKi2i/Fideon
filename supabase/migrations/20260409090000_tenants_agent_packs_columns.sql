-- Backward-compatible tenants columns required by signup wizard + trigger.
-- Fixes: column "agent_packs" does not exist (42703)

ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS agent_packs TEXT[] NOT NULL DEFAULT '{}'::text[],
  ADD COLUMN IF NOT EXISTS workflow_addon_slots INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS workflow_slots_total INTEGER,
  ADD COLUMN IF NOT EXISTS max_agent_packs INTEGER,
  ADD COLUMN IF NOT EXISTS max_active_models INTEGER;

-- Ensure legacy rows have sane defaults even if columns existed but were nullable.
UPDATE public.tenants
SET
  agent_packs = COALESCE(agent_packs, '{}'::text[]),
  workflow_addon_slots = COALESCE(workflow_addon_slots, 0)
WHERE agent_packs IS NULL
   OR workflow_addon_slots IS NULL;

