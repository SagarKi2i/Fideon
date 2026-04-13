/**
 * Maps signup wizard agent pack ids (see Signup.tsx AGENT_PACKS) to insurance marketplace model ids.
 * A model is unlocked for a tenant if it appears in at least one of the tenant's selected packs.
 */
export const AGENT_PACK_TO_MODEL_IDS: Record<string, readonly string[]> = {
  underwriting: [
    "quote-generation",
    "coverage-validation",
    "acord-parser",
    "carrier-submission-intake",
    "endorsement-intelligence",
    "risk-appetite",
    "broker-advisory",
    "premium-estimation",
    "mga-binding-authority",
    "mga-program-underwriting",
    "mga-capacity-matching",
    "carrier-submission-triage",
    "carrier-risk-scoring",
    "carrier-pricing-engine",
    "carrier-reinsurance",
  ],
  claims: [
    "claims-fnol",
    "carrier-claims-intake",
    "carrier-claims-adjudication",
    "carrier-fraud-detection",
    "carrier-subrogation",
  ],
  distribution: [
    "policy-comparison",
    "document-retrieval",
    "renewal-review",
    "communication-generator",
    "mga-bordereaux-generator",
    "mga-producer-management",
    "carrier-policy-issuance",
  ],
  compliance: [
    "compliance-checker",
    "red-flag-detector",
    "mga-treaty-compliance",
  ],
  "agentic-rag": ["multi-document", "document-retrieval"],
};

export function modelIdsForAgentPacks(packIds: string[]): Set<string> {
  const set = new Set<string>();
  for (const packId of packIds) {
    const ids = AGENT_PACK_TO_MODEL_IDS[packId];
    if (ids) for (const mid of ids) set.add(mid);
  }
  return set;
}
