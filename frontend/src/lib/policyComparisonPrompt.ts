import type { ExtractedDocumentText } from "@/lib/documentText";

export type PolicyComparisonStructured = {
  taxonomy: {
    domain: "insurance";
    doc_type_a: string;
    doc_type_b: string;
    lines_of_business: string[];
  };
  extracted_fields: {
    policyA: Record<string, unknown>;
    policyB: Record<string, unknown>;
  };
  clause_diff: {
    clauses: Array<{
      id: string;
      title?: string;
      status: "added" | "removed" | "changed";
      before?: string;
      after?: string;
      path?: string;
    }>;
    meta?: Record<string, unknown>;
  };
  deviation_percent: number;
  deviation_exceeds_threshold: boolean;
  recommendation?: {
    recommended_policy: "A" | "B" | "NEITHER";
    rationale: string[];
  };
  warnings: string[];
};

export function buildPolicyComparisonPrompt(params: {
  docA: ExtractedDocumentText;
  docB: ExtractedDocumentText;
  deviationThresholdPercent?: number;
}): string {
  const threshold = params.deviationThresholdPercent ?? 10;

  // Keep documents bounded to avoid overloading the model.
  // Use a conservative char budget; the backend/model can still truncate further.
  const maxChars = 40_000;
  const aText = params.docA.text.length > maxChars ? `${params.docA.text.slice(0, maxChars)}\n\n[TRUNCATED]` : params.docA.text;
  const bText = params.docB.text.length > maxChars ? `${params.docB.text.slice(0, maxChars)}\n\n[TRUNCATED]` : params.docB.text;

  return [
    "You are a policy checking engine for insurance documents.",
    "Compare two policy documents and produce a STRICT JSON object only (no markdown, no prose outside JSON).",
    "",
    "Rules:",
    `- Compute deviation_percent as a number 0..100. Treat it as the % of materially changed coverage/clauses vs the combined set of salient clauses you identify.`,
    `- Set deviation_exceeds_threshold = deviation_percent > ${threshold}.`,
    `- If deviation_exceeds_threshold is true, include recommendation with recommended_policy (A|B|NEITHER) and a short rationale list.`,
    "- Always include clause_diff in one of these shapes: { clauses: [...] } where each clause has status=added|removed|changed and before/after text when available.",
    "- Always include extracted_fields.policyA and extracted_fields.policyB with key fields you can reliably extract (carrier, premiums, limits, deductibles, effective dates, exclusions, endorsements, etc.).",
    "- Include taxonomy fields (domain, doc types, LOB).",
    "- If data is missing, keep keys but set values to null and add a warning.",
    "",
    "Output JSON schema:",
    "{",
    '  "taxonomy": { "domain": "insurance", "doc_type_a": string, "doc_type_b": string, "lines_of_business": string[] },',
    '  "extracted_fields": { "policyA": object, "policyB": object },',
    '  "clause_diff": { "clauses": [ { "id": string, "title"?: string, "status": "added"|"removed"|"changed", "before"?: string, "after"?: string, "path"?: string } ], "meta"?: object },',
    '  "deviation_percent": number,',
    '  "deviation_exceeds_threshold": boolean,',
    '  "recommendation"?: { "recommended_policy": "A"|"B"|"NEITHER", "rationale": string[] },',
    '  "warnings": string[]',
    "}",
    "",
    "Document A:",
    `Filename: ${params.docA.filename}`,
    `Mime: ${params.docA.mimeType}`,
    params.docA.pageCount ? `Pages: ${params.docA.pageCount}` : "",
    aText,
    "",
    "Document B:",
    `Filename: ${params.docB.filename}`,
    `Mime: ${params.docB.mimeType}`,
    params.docB.pageCount ? `Pages: ${params.docB.pageCount}` : "",
    bText,
  ]
    .filter(Boolean)
    .join("\n");
}

export function tryParsePolicyComparisonStructured(raw: string): PolicyComparisonStructured | null {
  if (!raw || !raw.trim()) return null;

  // Prefer JSON fenced blocks if the model ignored instructions.
  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  const candidate = fenced?.[1]?.trim() ?? raw.trim();

  const firstBrace = candidate.indexOf("{");
  const lastBrace = candidate.lastIndexOf("}");
  if (firstBrace === -1 || lastBrace === -1 || lastBrace <= firstBrace) return null;

  const sliced = candidate.slice(firstBrace, lastBrace + 1);
  try {
    return JSON.parse(sliced) as PolicyComparisonStructured;
  } catch {
    return null;
  }
}

