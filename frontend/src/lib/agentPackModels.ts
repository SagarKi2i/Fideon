/**
 * Maps agent pack IDs to insurance marketplace model IDs.
 * A model is accessible to a tenant if it appears in at least one of the tenant's packs.
 *
 * Pack structure (function-based, 5 packs — mirrors sir's doc v3):
 *   underwriting — quote generation, policy comparison, ACORD, coverage validation, risk tools
 *   claims       — FNOL, carrier claims intake, adjudication, fraud detection, subrogation
 *   distribution — document retrieval, renewal review, broker advisory, communication, loss runs
 *   mga          — all MGA segment pods
 *   carrier      — all Carrier segment pods
 *
 * A pod may belong to multiple packs (e.g. policy-comparison is in both underwriting + distribution).
 * The modelIdsForAgentPacks() union handles deduplication automatically.
 */
export const AGENT_PACK_TO_MODEL_IDS: Record<string, readonly string[]> = {
  underwriting: [
    "quote-generation",
    "policy-comparison",          // also in distribution
    "coverage-validation",
    "endorsement-intelligence",
    "acord_form_understanding",
    "compliance-checker",
    "risk-appetite",
    "multi-document",
    "red-flag-detector",
    "premium-estimation",
  ],
  claims: [
    "claims-fnol",
    "carrier-claims-intake",
    "carrier-claims-adjudication",
    "carrier-fraud-detection",
    "carrier-subrogation",
  ],
  distribution: [
    "policy-comparison",          // also in underwriting
    "document-retrieval",
    "renewal-review",
    "broker-advisory",
    "communication-generator",
    "loss-run-reporting",
  ],
  mga: [
    "mga-binding-authority",
    "mga-program-underwriting",
    "mga-bordereaux-generator",
    "mga-capacity-matching",
    "mga-producer-management",
    "mga-treaty-compliance",
  ],
  carrier: [
    "carrier-submission-intake",
    "carrier-submission-triage",
    "carrier-risk-scoring",
    "carrier-pricing-engine",
    "carrier-claims-intake",
    "carrier-claims-adjudication",
    "carrier-fraud-detection",
    "carrier-subrogation",
    "carrier-policy-issuance",
    "carrier-reinsurance",
  ],
};

export function modelIdsForAgentPacks(packIds: string[]): Set<string> {
  const set = new Set<string>();
  for (const packId of packIds) {
    const ids = AGENT_PACK_TO_MODEL_IDS[packId];
    if (ids) for (const mid of ids) set.add(mid);
  }
  return set;
}