-- Migration: 20260427200000_rename_agent_packs_to_segments.sql
--
-- Remaps all previous agent_packs values to the new 5-pack function-based structure.
--
-- Previous pack IDs (before this migration — two historical states possible):
--
--   State A — original function-based (pre-April 2026):
--     underwriting, claims, distribution, compliance, agentic-rag
--
--   State B — interim segment-based (briefly used April 2026):
--     brokers, mga, carriers, others
--
-- New pack IDs (sir's doc v3):
--   underwriting — quote gen, policy comparison, ACORD, coverage validation, risk tools
--   claims       — FNOL, carrier claims intake/adjudication, fraud detection, subrogation
--   distribution — document retrieval, renewal review, broker advisory, communication, loss runs
--   mga          — all MGA segment pods
--   carrier      — all Carrier segment pods
--
-- Remap logic:
--   underwriting → underwriting  (kept — same ID, same intent)
--   claims       → claims        (kept — same ID, same intent)
--   distribution → distribution  (kept — same ID, same intent)
--   compliance   → underwriting  (compliance pods now live in Underwriting Pack)
--   agentic-rag  → distribution  (RAG/document retrieval belongs in Distribution Pack)
--   brokers      → underwriting  (interim: conservative mapping; brokers most likely had UW use case)
--   carriers     → carrier       (interim: direct equivalent, note spelling change s→no-s)
--   mga          → mga           (kept — same ID)
--   others       → (dropped)     (no equivalent; pack had no pods)
--
-- Idempotent: runs already on the new pack IDs are left unchanged by the WHERE clause.

UPDATE public.tenants
SET agent_packs = ARRAY(
  SELECT DISTINCT new_pack
  FROM (
    SELECT
      CASE old_pack
        -- State A — original function-based packs
        WHEN 'underwriting'  THEN 'underwriting'
        WHEN 'claims'        THEN 'claims'
        WHEN 'distribution'  THEN 'distribution'
        WHEN 'compliance'    THEN 'underwriting'
        WHEN 'agentic-rag'   THEN 'distribution'
        -- State B — interim segment-based packs (April 2026)
        WHEN 'brokers'       THEN 'underwriting'
        WHEN 'carriers'      THEN 'carrier'
        WHEN 'mga'           THEN 'mga'
        -- 'others' → intentionally omitted (no equivalent pack)
        -- Pass through any value already in the new format
        ELSE old_pack
      END AS new_pack
    FROM unnest(agent_packs) AS old_pack
  ) sub
  -- Only keep valid new pack IDs — silently drops 'others' and unknown values
  WHERE new_pack IN ('underwriting', 'claims', 'distribution', 'mga', 'carrier')
)
WHERE agent_packs && ARRAY[
  'underwriting', 'claims', 'distribution', 'compliance', 'agentic-rag',
  'brokers', 'carriers', 'others'
]::text[];

-- Verify: warn if any old or unknown pack IDs remain
DO $$
DECLARE
  stale_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO stale_count
  FROM public.tenants
  WHERE agent_packs && ARRAY[
    'compliance', 'agentic-rag', 'brokers', 'carriers', 'others'
  ]::text[];

  IF stale_count > 0 THEN
    RAISE WARNING 'Migration incomplete: % tenant(s) still have unmapped pack IDs', stale_count;
  ELSE
    RAISE NOTICE 'Migration complete: all tenants now use the 5-pack function-based structure (underwriting / claims / distribution / mga / carrier)';
  END IF;
END $$;