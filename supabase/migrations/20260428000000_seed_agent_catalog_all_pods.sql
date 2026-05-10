-- Migration: 20260428000000_seed_agent_catalog_all_pods.sql
--
-- Seeds all 32 pods into agent_catalog (31 from sir's doc v3 + loss-run-reporting).
-- Each row provides the system_prompt and output_schema that pod_extraction.py
-- reads at runtime via _load_pod_agent_and_domain(pod_id).
--
-- ON CONFLICT DO UPDATE: safe to re-run. Existing system_prompt / output_schema
-- values are preserved (COALESCE) so manual admin edits are not overwritten.
--
-- Domain: all pods belong to domain_id = 'insurance' (must exist before this migration).

-- ─────────────────────────────────────────────────────────────────────────────
-- BROKER SEGMENT — 16 pods (15 from doc + loss-run-reporting)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.agent_catalog (
  id, display_name, domain_id, category, description, system_prompt, output_schema, tools, is_active
) VALUES

-- 1. Quote Generation
(
  'quote-generation',
  'Quote Generation Agent',
  'insurance',
  'Automation',
  'Generates structured multi-carrier insurance quote comparisons from applicant data.',
  'You are a structured insurance quote generation engine. You receive applicant information and coverage requirements and produce a detailed multi-carrier quote comparison in strict JSON. Output only valid JSON matching the output schema — no markdown, no prose outside the JSON object. Generate realistic but clearly simulated premium estimates. If a carrier is unlikely to write a risk, set status to "declined" with a reason.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "QuoteGenerationOutput",
    "type": "object",
    "required": ["insurance_type", "applicant", "quotes"],
    "properties": {
      "insurance_type": { "type": "string" },
      "applicant": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "business_name": { "type": ["string", "null"] },
          "email": { "type": "string" },
          "phone": { "type": ["string", "null"] },
          "address": { "type": "string" },
          "coverage_amount": { "type": "number" }
        }
      },
      "quotes": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["carrier", "premium", "coverage", "deductible", "status"],
          "properties": {
            "carrier": { "type": "string" },
            "premium": { "type": "number" },
            "coverage": { "type": "number" },
            "deductible": { "type": "number" },
            "features": { "type": "array", "items": { "type": "string" } },
            "status": { "type": "string", "enum": ["quoted", "declined", "referred"] },
            "financial_strength": { "type": ["string", "null"] },
            "decline_reason": { "type": ["string", "null"] }
          }
        }
      },
      "recommendation": { "type": ["string", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 2. Policy Comparison
(
  'policy-comparison',
  'Policy Comparison Engine',
  'insurance',
  'Analysis',
  'Performs deep structural comparison of two insurance policy documents.',
  'You are a structured insurance policy comparison engine. You receive paired extraction results for Policy A and Policy B and produce a detailed clause-level comparison in strict JSON. Output only valid JSON matching the output schema. Compute deviation_percent as 0-100. Assign materiality_score 0.0-1.0 to each changed clause (1.0 = critical coverage change). Set deviation_exceeds_threshold when deviation_percent > threshold. Always include extracted_fields for both policies. If data is missing, keep keys with null values.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PolicyComparisonOutput",
    "type": "object",
    "required": ["taxonomy", "extracted_fields", "clause_diff", "deviation_percent", "deviation_exceeds_threshold"],
    "properties": {
      "taxonomy": {
        "type": "object",
        "properties": {
          "domain": { "type": "string" },
          "doc_type_a": { "type": "string" },
          "doc_type_b": { "type": "string" },
          "lines_of_business": { "type": "array", "items": { "type": "string" } }
        }
      },
      "extracted_fields": {
        "type": "object",
        "properties": {
          "policyA": { "type": "object" },
          "policyB": { "type": "object" }
        }
      },
      "clause_diff": {
        "type": "object",
        "properties": {
          "clauses": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "id": { "type": "string" },
                "title": { "type": "string" },
                "status": { "type": "string", "enum": ["added", "removed", "changed"] },
                "before": { "type": ["string", "null"] },
                "after": { "type": ["string", "null"] },
                "materiality_score": { "type": "number", "minimum": 0, "maximum": 1 }
              }
            }
          }
        }
      },
      "deviation_percent": { "type": "number", "minimum": 0, "maximum": 100 },
      "deviation_exceeds_threshold": { "type": "boolean" },
      "recommendation": { "type": ["object", "null"] },
      "warnings": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 3. Coverage Validation
(
  'coverage-validation',
  'Coverage Validation & Eligibility',
  'insurance',
  'Validation',
  'Validates business eligibility, binding authority compliance, and coverage adequacy.',
  'You are a structured insurance coverage validation engine. You receive business details and coverage requirements and produce a structured eligibility and validation report in strict JSON. Check binding authority limits, admitted/non-admitted status, NAICS/SIC classification, and state-specific requirements. Flag any compliance gaps clearly.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CoverageValidationOutput",
    "type": "object",
    "required": ["eligibility_status", "binding_authority_check"],
    "properties": {
      "eligibility_status": { "type": "string", "enum": ["eligible", "ineligible", "refer", "declined"] },
      "binding_authority_check": {
        "type": "object",
        "properties": {
          "within_authority": { "type": "boolean" },
          "max_premium": { "type": ["number", "null"] },
          "notes": { "type": ["string", "null"] }
        }
      },
      "coverage_gaps": { "type": "array", "items": { "type": "string" } },
      "compliance_flags": { "type": "array", "items": { "type": "string" } },
      "recommended_limits": { "type": ["object", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 4. Endorsement Intelligence
(
  'endorsement-intelligence',
  'Endorsement Intelligence',
  'insurance',
  'Advisory',
  'Recommends required and optional endorsements based on business operations and contracts.',
  'You are a structured insurance endorsement recommendation engine. You receive business type, operations, state, and contract requirements and produce a structured endorsement recommendation report in strict JSON. Identify required endorsements (legally or contractually mandated) and recommended endorsements (risk management best practice). Estimate cost impact where possible.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "EndorsementIntelligenceOutput",
    "type": "object",
    "required": ["required_endorsements", "recommended_endorsements"],
    "properties": {
      "required_endorsements": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "code": { "type": "string" },
            "name": { "type": "string" },
            "reason": { "type": "string" },
            "cost_impact_estimate": { "type": ["string", "null"] }
          }
        }
      },
      "recommended_endorsements": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "code": { "type": "string" },
            "name": { "type": "string" },
            "reason": { "type": "string" },
            "cost_impact_estimate": { "type": ["string", "null"] }
          }
        }
      },
      "summary": { "type": ["string", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 5. Claims FNOL
(
  'claims-fnol',
  'Claims & FNOL Intelligence',
  'insurance',
  'Claims',
  'Processes First Notice of Loss documents and produces structured claim analysis.',
  'You are a structured insurance FNOL (First Notice of Loss) analysis engine. You receive an incident description and optionally extracted data from supporting documents (police reports, repair estimates, photos) and produce a structured FNOL analysis in strict JSON. Identify loss type, coverage triggers, parties, subrogation potential, and fraud indicators. Output only valid JSON matching the output schema.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FNOLInferenceOutput",
    "type": "object",
    "required": ["incident_date", "loss_type", "line_of_business"],
    "properties": {
      "incident_date": { "type": ["string", "null"] },
      "incident_location": { "type": ["string", "null"] },
      "loss_type": { "type": "string" },
      "line_of_business": { "type": "string" },
      "estimated_damage": { "type": ["number", "null"] },
      "parties_involved": { "type": "array", "items": { "type": "object" } },
      "coverage_assessment": { "type": ["string", "null"] },
      "documentation_checklist": { "type": "array", "items": { "type": "string" } },
      "recommended_next_steps": { "type": "array", "items": { "type": "string" } },
      "subrogation_flag": { "type": "boolean" },
      "fraud_indicators": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 6. Document Retrieval
(
  'document-retrieval',
  'Document Retrieval',
  'insurance',
  'Document Processing',
  'Retrieves policy documents from carrier portals and attaches them to AMS records.',
  'You are a structured insurance document retrieval coordinator. You receive carrier and policy details and produce a structured retrieval plan and status report in strict JSON. List documents to retrieve, carrier portal access steps, and AMS attachment instructions.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "DocumentRetrievalOutput",
    "type": "object",
    "required": ["retrieved"],
    "properties": {
      "session_id": { "type": ["string", "null"] },
      "retrieved": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": { "type": "string" },
            "type": { "type": "string" },
            "carrier": { "type": "string" },
            "ams_location": { "type": ["string", "null"] },
            "status": { "type": "string", "enum": ["retrieved", "pending", "failed", "not_found"] }
          }
        }
      },
      "failed": { "type": "array", "items": { "type": "object" } },
      "summary": { "type": ["string", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 7. Renewal Review
(
  'renewal-review',
  'Renewal Review Assistant',
  'insurance',
  'Analysis',
  'Compares expiring vs renewal policies and produces a structured change summary.',
  'You are a structured insurance renewal review engine. You receive paired expiring and renewal policy extraction results and produce a detailed change analysis in strict JSON. Compute premium change, identify coverage changes, and flag any gaps or improvements. Recommend action if material changes are detected.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "RenewalReviewOutput",
    "type": "object",
    "required": ["premium_change", "coverage_changes"],
    "properties": {
      "premium_change": {
        "type": "object",
        "properties": {
          "amount": { "type": "number" },
          "percent": { "type": "number" },
          "direction": { "type": "string", "enum": ["increase", "decrease", "unchanged"] }
        }
      },
      "coverage_changes": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "field": { "type": "string" },
            "before": { "type": ["string", "null"] },
            "after": { "type": ["string", "null"] },
            "materiality": { "type": "string", "enum": ["critical", "significant", "minor"] }
          }
        }
      },
      "new_exclusions": { "type": "array", "items": { "type": "string" } },
      "removed_coverages": { "type": "array", "items": { "type": "string" } },
      "recommendation": { "type": ["string", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 8. Compliance Checker
(
  'compliance-checker',
  'Compliance Checker',
  'insurance',
  'Validation',
  'Validates state regulations, surplus lines rules, and cancellation notice requirements.',
  'You are a structured insurance compliance validation engine. You receive policy and carrier details and produce a structured compliance check report in strict JSON. Validate admitted/non-admitted status, cancellation notice requirements, surplus lines filing obligations, and state-specific rules. Flag any violations or risks clearly.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ComplianceCheckerOutput",
    "type": "object",
    "required": ["admitted_status", "cancellation_compliance"],
    "properties": {
      "admitted_status": { "type": "string", "enum": ["admitted", "non-admitted", "unknown"] },
      "cancellation_compliance": {
        "type": "object",
        "properties": {
          "required_days": { "type": "number" },
          "provided_days": { "type": "number" },
          "compliant": { "type": "boolean" }
        }
      },
      "surplus_lines_required": { "type": "boolean" },
      "violations": { "type": "array", "items": { "type": "string" } },
      "warnings": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 9. Risk Appetite
(
  'risk-appetite',
  'Underwriting Risk Appetite Matching',
  'insurance',
  'Underwriting',
  'Matches risks with carrier appetite and returns ranked carrier recommendations.',
  'You are a structured underwriting risk appetite matching engine. You receive risk details (industry, revenue, employees, state, loss history) and produce a ranked list of carrier matches with estimated premium ranges and appetite scores in strict JSON. Score each carrier 0-100. Flag reasons for high or low appetite match.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "RiskAppetiteOutput",
    "type": "object",
    "required": ["carrier_matches"],
    "properties": {
      "carrier_matches": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "carrier": { "type": "string" },
            "match_score": { "type": "number", "minimum": 0, "maximum": 100 },
            "match_reasons": { "type": "array", "items": { "type": "string" } },
            "estimated_premium_range": { "type": ["string", "null"] },
            "appetite_flags": { "type": "array", "items": { "type": "string" } }
          }
        }
      },
      "recommended_carrier": { "type": ["string", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 10. Broker Advisory
(
  'broker-advisory',
  'Broker Advisory Engine',
  'insurance',
  'Advisory',
  'Identifies underinsurance gaps and recommends coverage enhancements.',
  'You are a structured broker advisory engine. You receive client details and optionally extracted coverage data and produce a structured advisory report identifying underinsurance gaps and coverage recommendations in strict JSON. Quantify the gap where possible and prioritise recommendations by severity.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "BrokerAdvisoryOutput",
    "type": "object",
    "required": ["underinsurance_gaps"],
    "properties": {
      "underinsurance_gaps": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "coverage": { "type": "string" },
            "current_limit": { "type": ["number", "null"] },
            "recommended_limit": { "type": ["number", "null"] },
            "gap_amount": { "type": ["number", "null"] },
            "severity": { "type": "string", "enum": ["critical", "significant", "minor"] }
          }
        }
      },
      "coverage_recommendations": { "type": "array", "items": { "type": "string" } },
      "summary": { "type": ["string", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 11. Multi-Document Analysis
(
  'multi-document',
  'Multi-Document Analysis',
  'insurance',
  'Document Processing',
  'Analyses multiple insurance documents simultaneously and identifies inconsistencies.',
  'You are a structured multi-document insurance analysis engine. You receive extraction results from 2-8 insurance documents and produce a structured inconsistency and cross-document analysis report in strict JSON. Identify data conflicts, missing information, and cross-document risks. Classify inconsistencies as critical, significant, or minor.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MultiDocumentOutput",
    "type": "object",
    "required": ["documents_analysed", "inconsistencies"],
    "properties": {
      "documents_analysed": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "index": { "type": "number" },
            "type": { "type": "string" },
            "key_fields": { "type": "object" }
          }
        }
      },
      "inconsistencies": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "type": { "type": "string", "enum": ["critical", "significant", "minor"] },
            "description": { "type": "string" },
            "documents_involved": { "type": "array", "items": { "type": "number" } }
          }
        }
      },
      "summary": { "type": ["string", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 12. Communication Generator
(
  'communication-generator',
  'Client Communication Generator',
  'insurance',
  'Communication',
  'Generates professional client emails, renewal letters, and proposal packets.',
  'You are a structured insurance client communication generator. You receive communication type, client details, and policy context and produce a polished, professional communication in strict JSON. Generate subject line, email body (in markdown), key points summary, and call-to-action. Match the tone to the communication type (formal for renewals, warm for proposals).',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CommunicationGeneratorOutput",
    "type": "object",
    "required": ["subject_line", "email_body"],
    "properties": {
      "subject_line": { "type": "string" },
      "email_body": { "type": "string" },
      "key_points_summary": { "type": "array", "items": { "type": "string" } },
      "call_to_action": { "type": ["string", "null"] },
      "suggested_follow_up_date": { "type": ["string", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 13. Red Flag Detector
(
  'red-flag-detector',
  'Red Flag Detector',
  'insurance',
  'Validation',
  'Identifies missing signatures, compliance gaps, and errors across insurance documents.',
  'You are a structured insurance document red flag detection engine. You receive extracted data from 1-10 insurance documents and produce a structured red flag report in strict JSON. Classify flags as critical, significant, or minor. Include the specific document index, field name, and clear description for each flag.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "RedFlagDetectorOutput",
    "type": "object",
    "required": ["flags"],
    "properties": {
      "flags": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "severity": { "type": "string", "enum": ["critical", "significant", "minor"] },
            "type": { "type": "string" },
            "description": { "type": "string" },
            "document_index": { "type": ["number", "null"] },
            "field": { "type": ["string", "null"] }
          }
        }
      },
      "critical_count": { "type": "number" },
      "significant_count": { "type": "number" },
      "minor_count": { "type": "number" },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 14. Premium Estimation
(
  'premium-estimation',
  'Premium Estimation Helper',
  'insurance',
  'Pricing',
  'Provides indicative premium ranges across lines of business based on risk characteristics.',
  'You are a structured insurance premium estimation engine. You receive risk characteristics (industry, revenue, employees, state, years in business, loss history) and produce indicative premium ranges per line of business in strict JSON. Provide low, high, and median estimates. Clearly mark these as indicative, not binding quotes.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PremiumEstimationOutput",
    "type": "object",
    "required": ["premium_estimates"],
    "properties": {
      "premium_estimates": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "line": { "type": "string" },
            "low": { "type": "number" },
            "high": { "type": "number" },
            "median": { "type": "number" }
          }
        }
      },
      "total_low": { "type": "number" },
      "total_high": { "type": "number" },
      "total_median": { "type": "number" },
      "disclaimer": { "type": "string" },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 15. Loss Run Reporting (new pod — not in sir's doc v3, added per team decision)
(
  'loss-run-reporting',
  'Loss Run Reporting',
  'insurance',
  'Analytics',
  'Ingests carrier loss runs, consolidates 5-year claims history, and generates underwriter-ready reports.',
  'You are a structured insurance loss run reporting engine. You receive carrier loss run data (extracted from PDFs or structured input) and produce a consolidated 5-year claims history report in strict JSON. Compute loss ratios, frequency trends, and severity trends. Flag adverse development. Format output for submission to underwriters.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "LossRunReportingOutput",
    "type": "object",
    "required": ["policy_years", "totals"],
    "properties": {
      "policy_years": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "year": { "type": "string" },
            "carrier": { "type": "string" },
            "written_premium": { "type": ["number", "null"] },
            "claims_count": { "type": "number" },
            "total_incurred": { "type": "number" },
            "total_paid": { "type": "number" },
            "total_reserved": { "type": "number" },
            "loss_ratio": { "type": ["number", "null"] }
          }
        }
      },
      "totals": {
        "type": "object",
        "properties": {
          "five_year_incurred": { "type": "number" },
          "five_year_paid": { "type": "number" },
          "average_loss_ratio": { "type": ["number", "null"] },
          "claim_frequency_trend": { "type": "string", "enum": ["improving", "stable", "deteriorating"] },
          "severity_trend": { "type": "string", "enum": ["improving", "stable", "deteriorating"] }
        }
      },
      "adverse_development_flags": { "type": "array", "items": { "type": "string" } },
      "underwriter_summary": { "type": ["string", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- ─────────────────────────────────────────────────────────────────────────────
-- MGA SEGMENT — 6 pods
-- ─────────────────────────────────────────────────────────────────────────────

-- 16. MGA Binding Authority
(
  'mga-binding-authority',
  'Binding Authority Manager',
  'insurance',
  'Authority Management',
  'Monitors binding authority utilisation, limits, and compliance across MGA programs.',
  'You are a structured MGA binding authority management engine. You receive program authority limits and current utilisation data and produce a structured authority status report in strict JSON. Flag programmes approaching capacity limits (amber: >80%, red: >95%). Identify any out-of-appetite or out-of-territory risks.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "BindingAuthorityOutput",
    "type": "object",
    "required": ["utilisation_pct", "utilisation_status"],
    "properties": {
      "utilisation_pct": { "type": "number", "minimum": 0, "maximum": 100 },
      "utilisation_status": { "type": "string", "enum": ["green", "amber", "red"] },
      "approaching_cap_flags": { "type": "array", "items": { "type": "string" } },
      "out_of_appetite_risks": { "type": "array", "items": { "type": "string" } },
      "remaining_capacity": { "type": ["number", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 17. MGA Program Underwriting
(
  'mga-program-underwriting',
  'Program Underwriting Engine',
  'insurance',
  'Underwriting',
  'Evaluates risks against MGA program appetite and produces structured underwriting decisions.',
  'You are a structured MGA program underwriting engine. You receive risk details and program appetite parameters and produce a structured underwriting decision in strict JSON. Score the risk 0-100. Decide approve/refer/decline with clear eligibility check results and premium indication.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ProgramUnderwritingOutput",
    "type": "object",
    "required": ["risk_score", "decision"],
    "properties": {
      "risk_score": { "type": "number", "minimum": 0, "maximum": 100 },
      "decision": { "type": "string", "enum": ["approve", "refer", "decline"] },
      "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
      "eligibility_checks": { "type": "array", "items": { "type": "object" } },
      "premium_indication": { "type": ["number", "null"] },
      "refer_reasons": { "type": "array", "items": { "type": "string" } },
      "decline_reasons": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 18. MGA Bordereaux Generator
(
  'mga-bordereaux-generator',
  'Bordereaux Generator',
  'insurance',
  'Reporting',
  'Generates structured premium and claims bordereaux reports for carrier submission.',
  'You are a structured MGA bordereaux generation engine. You receive period, program, and transaction data and produce a structured bordereaux report in strict JSON. Include new business, renewals, cancellations, and claims summary. Format for carrier submission.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "BordereauxGeneratorOutput",
    "type": "object",
    "required": ["bordereaux_report"],
    "properties": {
      "bordereaux_report": {
        "type": "object",
        "properties": {
          "period": { "type": "string" },
          "program": { "type": "string" },
          "carrier": { "type": "string" },
          "new_business": { "type": "object" },
          "renewals": { "type": "object" },
          "cancellations": { "type": "object" },
          "claims_summary": { "type": "object" },
          "net_premium": { "type": "number" }
        }
      },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 19. MGA Capacity Matching
(
  'mga-capacity-matching',
  'Capacity Matching Engine',
  'insurance',
  'Placement',
  'Matches risks with available reinsurance capacity and returns structured placement options.',
  'You are a structured MGA capacity matching engine. You receive risk details (TIV, coverage type, territory, attachment point) and produce a structured list of capacity matches in strict JSON. Score each match and estimate pricing indication. Identify any capacity gaps.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CapacityMatchingOutput",
    "type": "object",
    "required": ["capacity_match"],
    "properties": {
      "capacity_match": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "carrier": { "type": "string" },
            "available_capacity": { "type": "number" },
            "pct_share": { "type": "number" },
            "pricing_indication": { "type": ["string", "null"] },
            "match_score": { "type": "number", "minimum": 0, "maximum": 100 }
          }
        }
      },
      "capacity_gap": { "type": ["number", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 20. MGA Producer Management
(
  'mga-producer-management',
  'Producer Management Hub',
  'insurance',
  'Distribution',
  'Analyses producer performance metrics and generates structured management reports.',
  'You are a structured MGA producer performance analysis engine. You receive producer data (written premium, policy count, loss ratio, complaints) for a given period and produce a structured performance report in strict JSON. Rank the producer, identify trends, and flag any performance concerns.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ProducerManagementOutput",
    "type": "object",
    "required": ["performance_summary"],
    "properties": {
      "performance_summary": {
        "type": "object",
        "properties": {
          "rank": { "type": ["string", "null"] },
          "vs_last_year_pct": { "type": ["number", "null"] },
          "loss_ratio_status": { "type": "string", "enum": ["good", "acceptable", "concern", "critical"] }
        }
      },
      "production_metrics": { "type": "object" },
      "performance_flags": { "type": "array", "items": { "type": "string" } },
      "recommendations": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 21. MGA Treaty Compliance
(
  'mga-treaty-compliance',
  'Treaty Compliance Monitor',
  'insurance',
  'Compliance',
  'Monitors reinsurance treaty compliance and financial position for MGA programs.',
  'You are a structured MGA treaty compliance monitoring engine. You receive treaty terms and YTD financial data and produce a structured compliance and financial summary report in strict JSON. Flag any treaty limit breaches, cession rate anomalies, or upcoming renewal actions required.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "TreatyComplianceOutput",
    "type": "object",
    "required": ["compliance_status"],
    "properties": {
      "compliance_status": { "type": "string", "enum": ["compliant", "warning", "breach"] },
      "financial_summary": { "type": "object" },
      "compliance_flags": { "type": "array", "items": { "type": "string" } },
      "actions_required": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- ─────────────────────────────────────────────────────────────────────────────
-- CARRIER SEGMENT — 10 pods
-- ─────────────────────────────────────────────────────────────────────────────

-- 22. Carrier Submission Intake
(
  'carrier-submission-intake',
  'Submission Intake Engine',
  'insurance',
  'Submission Processing',
  'Processes inbound broker submissions and produces structured triage scoring.',
  'You are a structured carrier submission intake and triage engine. You receive broker submission data (extracted from documents or structured input) and produce a structured triage report in strict JSON. Score 0-100. Classify priority. Identify appetite fit and missing information.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "SubmissionIntakeOutput",
    "type": "object",
    "required": ["triage_score", "priority"],
    "properties": {
      "triage_score": { "type": "number", "minimum": 0, "maximum": 100 },
      "priority": { "type": "string", "enum": ["high", "medium", "low", "decline"] },
      "classification": { "type": "object" },
      "appetite_fit": { "type": "string", "enum": ["strong", "moderate", "weak", "decline"] },
      "missing_information": { "type": "array", "items": { "type": "string" } },
      "next_steps": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 23. Carrier Submission Triage
(
  'carrier-submission-triage',
  'Submission Triage Agent',
  'insurance',
  'Submission Processing',
  'Prioritises and routes submission queues for carrier underwriting teams.',
  'You are a structured carrier submission queue triage agent. You receive a snapshot of queued submissions and produce a prioritised ranking with routing recommendations in strict JSON. Rank submissions by urgency, appetite fit, and premium potential.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "SubmissionTriageOutput",
    "type": "object",
    "required": ["prioritised_queue"],
    "properties": {
      "prioritised_queue": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "rank": { "type": "number" },
            "submission_id": { "type": "string" },
            "priority": { "type": "string", "enum": ["critical", "high", "medium", "low"] },
            "appetite_score": { "type": "number", "minimum": 0, "maximum": 100 },
            "routing": { "type": ["string", "null"] },
            "reason": { "type": "string" }
          }
        }
      },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 24. Carrier Risk Scoring
(
  'carrier-risk-scoring',
  'Risk Scoring Model',
  'insurance',
  'Underwriting',
  'Produces structured risk scores and tier classifications for carrier underwriting.',
  'You are a structured carrier risk scoring engine. You receive risk characteristics (industry, revenue, employees, locations, loss history, risk controls) and produce a structured risk score and tier classification in strict JSON. Score 0-100 overall and by component. Assign risk tier and provide component explanations.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "RiskScoringOutput",
    "type": "object",
    "required": ["overall_score", "risk_tier"],
    "properties": {
      "overall_score": { "type": "number", "minimum": 0, "maximum": 100 },
      "risk_tier": { "type": "string", "enum": ["preferred", "standard", "substandard", "decline"] },
      "component_scores": { "type": "object" },
      "risk_factors": { "type": "array", "items": { "type": "string" } },
      "mitigation_credits": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 25. Carrier Pricing Engine
(
  'carrier-pricing-engine',
  'Actuarial Pricing Engine',
  'insurance',
  'Pricing',
  'Produces structured technical premium calculations for carrier underwriting.',
  'You are a structured actuarial pricing engine. You receive risk class, line of business, TIV/revenue, limits, deductibles, and loss history and produce a detailed technical premium calculation in strict JSON. Show each pricing component, loading factor, and final technical premium. Flag any unusual rating factors.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PricingEngineOutput",
    "type": "object",
    "required": ["technical_premium_calculation"],
    "properties": {
      "technical_premium_calculation": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "component": { "type": "string" },
            "base": { "type": "number" },
            "factor": { "type": "number" },
            "result": { "type": "number" }
          }
        }
      },
      "final_technical_premium": { "type": "number" },
      "pricing_flags": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 26. Carrier Claims Intake
(
  'carrier-claims-intake',
  'Claims Intake Processor',
  'insurance',
  'Claims Processing',
  'Processes inbound claim notifications and produces structured intake records.',
  'You are a structured carrier claims intake processor. You receive claim notification details (policy number, claimant, loss date, cause of loss) and produce a structured intake record in strict JSON. Verify policy coverage, set initial reserve indication, assign handler, and identify immediate investigation priorities.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ClaimsIntakeOutput",
    "type": "object",
    "required": ["claim_number", "policy_verified"],
    "properties": {
      "claim_number": { "type": "string" },
      "policy_verified": {
        "type": "object",
        "properties": {
          "active": { "type": "boolean" },
          "coverage_type": { "type": "string" },
          "limits": { "type": ["object", "null"] },
          "deductible": { "type": ["number", "null"] }
        }
      },
      "initial_reserve": { "type": ["number", "null"] },
      "assigned_handler": { "type": ["string", "null"] },
      "investigation_priorities": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 27. Carrier Claims Adjudication
(
  'carrier-claims-adjudication',
  'Claims Adjudication Engine',
  'insurance',
  'Claims Processing',
  'Adjudicates claims against policy terms and produces structured coverage determinations.',
  'You are a structured carrier claims adjudication engine. You receive claim details, policy terms, and extracted document evidence and produce a structured coverage determination and settlement recommendation in strict JSON. Determine coverage applicability per coverage line, recommend settlement amount, and flag any subrogation or fraud potential.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ClaimsAdjudicationOutput",
    "type": "object",
    "required": ["coverage_determination"],
    "properties": {
      "coverage_determination": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "coverage": { "type": "string" },
            "applicable": { "type": "boolean" },
            "limit": { "type": ["number", "null"] },
            "deductible": { "type": ["number", "null"] },
            "available": { "type": ["number", "null"] }
          }
        }
      },
      "settlement_recommendation": { "type": ["number", "null"] },
      "reserve_adjustment": { "type": ["number", "null"] },
      "subrogation_flag": { "type": "boolean" },
      "fraud_flag": { "type": "boolean" },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 28. Carrier Fraud Detection
(
  'carrier-fraud-detection',
  'Claims Fraud Detector',
  'insurance',
  'Claims Processing',
  'Analyses claims for fraud indicators and produces structured risk assessments.',
  'You are a structured insurance claims fraud detection engine. You receive claimant profile, claim details, and optionally extracted document evidence and produce a structured fraud risk assessment in strict JSON. Score 0-100. Identify specific fraud indicators with evidence. Recommend investigation actions.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FraudDetectionOutput",
    "type": "object",
    "required": ["fraud_score", "risk_level"],
    "properties": {
      "fraud_score": { "type": "number", "minimum": 0, "maximum": 100 },
      "risk_level": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
      "indicators": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "indicator": { "type": "string" },
            "evidence": { "type": "string" },
            "weight": { "type": "number", "minimum": 0, "maximum": 1 }
          }
        }
      },
      "recommended_actions": { "type": "array", "items": { "type": "string" } },
      "siu_referral": { "type": "boolean" },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 29. Carrier Subrogation
(
  'carrier-subrogation',
  'Subrogation Recovery Agent',
  'insurance',
  'Claims Processing',
  'Identifies subrogation recovery opportunities and produces structured recovery plans.',
  'You are a structured insurance subrogation recovery analysis engine. You receive claim details, cause of loss, and optionally extracted document evidence (contracts, maintenance records) and produce a structured subrogation opportunity assessment in strict JSON. Estimate recovery probability and potential amount. Identify liable third parties.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "SubrogationOutput",
    "type": "object",
    "required": ["recovery_potential"],
    "properties": {
      "recovery_potential": { "type": "string", "enum": ["low", "medium", "high"] },
      "recovery_probability_pct": { "type": "number", "minimum": 0, "maximum": 100 },
      "targets": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "party": { "type": "string" },
            "liability_basis": { "type": "string" },
            "estimated_recovery": { "type": ["number", "null"] }
          }
        }
      },
      "recommended_actions": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 30. Carrier Policy Issuance
(
  'carrier-policy-issuance',
  'Policy Issuance Engine',
  'insurance',
  'Policy Admin',
  'Validates bound quote documents and produces structured policy issuance readiness reports.',
  'You are a structured carrier policy issuance validation engine. You receive bound quote reference and extracted documents (signed application, payment confirmation, supporting docs) and produce a structured issuance readiness report in strict JSON. Verify all required fields, signatures, and payments are present. Flag any blockers.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PolicyIssuanceOutput",
    "type": "object",
    "required": ["issuance_validation"],
    "properties": {
      "issuance_validation": {
        "type": "object",
        "properties": {
          "all_fields_complete": { "type": "boolean" },
          "payment_confirmed": { "type": "boolean" },
          "signatures_present": { "type": "boolean" }
        }
      },
      "blockers": { "type": "array", "items": { "type": "string" } },
      "warnings": { "type": "array", "items": { "type": "string" } },
      "issuance_ready": { "type": "boolean" },
      "policy_number_format": { "type": ["string", "null"] },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
),

-- 31. Carrier Reinsurance
(
  'carrier-reinsurance',
  'Reinsurance Manager',
  'insurance',
  'Reinsurance',
  'Analyses reinsurance treaty performance and produces structured cession reports.',
  'You are a structured carrier reinsurance management engine. You receive treaty structure and YTD financial data and produce a structured treaty performance report in strict JSON. Calculate ceded premium, recoveries, loss ratios, and profit commissions per layer. Flag any adverse treaty development.',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ReinsuranceOutput",
    "type": "object",
    "required": ["treaty_performance"],
    "properties": {
      "treaty_performance": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "layer": { "type": "string" },
            "ceded_premium": { "type": "number" },
            "recoveries": { "type": "number" },
            "loss_ratio": { "type": "number" },
            "profit_commission": { "type": ["number", "null"] }
          }
        }
      },
      "net_position": { "type": "object" },
      "adverse_development_flags": { "type": "array", "items": { "type": "string" } },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    }
  }'::jsonb,
  '{"extraction_strategy": "generic_structured_llm"}'::jsonb,
  true
)

ON CONFLICT (id) DO UPDATE SET
  display_name  = EXCLUDED.display_name,
  domain_id     = EXCLUDED.domain_id,
  category      = EXCLUDED.category,
  description   = EXCLUDED.description,
  -- Preserve manually edited system_prompt and output_schema; only seed if currently empty
  system_prompt = COALESCE(NULLIF(public.agent_catalog.system_prompt, ''), EXCLUDED.system_prompt),
  output_schema = CASE
    WHEN public.agent_catalog.output_schema IS NULL OR public.agent_catalog.output_schema = '{}'::jsonb
    THEN EXCLUDED.output_schema
    ELSE public.agent_catalog.output_schema
  END,
  tools         = COALESCE(public.agent_catalog.tools, EXCLUDED.tools),
  is_active     = true;

-- Verify seeding
DO $$
DECLARE
  pod_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO pod_count
  FROM public.agent_catalog
  WHERE domain_id = 'insurance' AND is_active = true;

  RAISE NOTICE 'agent_catalog now has % active insurance pods', pod_count;
END $$;