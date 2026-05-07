import asyncio
import re
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile
import httpx

from app.core.config import (
    GROQ_API_KEY,
    GROQ_OPENAI_COMPAT_URL,
    GROQ_MODEL_CHAT,
    OPENAI_API_KEY,
    OPENAI_CHAT_COMPLETIONS_URL,
    OPENAI_MODEL,
    RUNPOD_GENERATE_URL,
    FIDEON_SECRET_KEY,
    RUNPOD_API_KEY,
    RUNPOD_MODEL_LLAMA,
)
import logging

from app.core.supabase import verify_user
from Models.acord_form_understanding import AcordFormSummary

from app.routes.acord import _extract_summary_from_file, _ensure_runpod_ready_for_acord

logger = logging.getLogger("fideon.policy_comparison")
router = APIRouter()

# ── LOB-specific field workbooks ──────────────────────────────────────────────
_LOB_FIELDS: dict[str, list[str]] = {
    "commercial-auto": [
        "named_insured", "mailing_address", "agency", "agency_address",
        "policy_number", "coverage_period_start", "coverage_period_end",
        "policy_premium", "carrier", "full_location_schedules",
        "owned_auto_liability_symbol", "collision_coverage_symbol",
        "comprehensive_coverage_symbol", "underinsured_motorist_symbol",
        "uninsured_motorist_symbol", "non_owned_auto_symbol",
        "hired_car_symbol", "medical_payments_symbol",
        "liability", "underinsured_motorist", "uninsured_motorist",
        "non_owned_auto", "hired_car", "medical_payments",
        "number_of_vehicles", "vehicle_1_year", "vehicle_1_make", "vehicle_1_model",
        "vehicle_1_vin", "vehicle_1_coverage_type", "vehicle_1_limit",
        "vehicle_1_comp_coll_deductible", "vehicle_1_premium",
        "form_CA_00_01", "form_CA_02_70", "form_CA_21_17"
    ],
    "crime": [
        "named_insured", "policy_number", "carrier", "coverage_effective_date",
        "coverage_expiration_date", "employee_theft_limit", "forgery_limit",
        "computer_fraud_limit", "funds_transfer_fraud_limit", "inside_premises_theft_limit",
        "outside_premises_limit", "deductible", "discovery_period", "retroactive_date",
        "territory", "covered_locations", "number_of_employees", "third_party_coverage",
        "erisa_coverage", "client_property_coverage", "money_orders_coverage",
        "counterfeit_currency_coverage", "safe_burglary_coverage", "robbery_coverage",
        "messenger_coverage", "premises_coverage", "custodian_coverage", "audit_frequency",
        "cancellation_provision", "aggregate_limit", "occurrence_limit", "loss_sustained_basis",
        "discovery_basis", "employee_dishonesty_form", "faithful_performance_coverage",
        "public_employee_dishonesty", "tenant_discrimination", "identity_fraud_expense",
        "social_engineering_fraud", "cyber_deception_coverage", "securities_coverage",
        "inventory_shortage_exclusion", "voluntary_parting_exclusion", "prior_loss_history",
        "pending_claims", "supplemental_forms", "endorsements", "coinsurance_percentage",
        "waiting_period", "joint_insureds", "additional_insureds", "premium_amount",
        "minimum_earned_premium", "broker_name", "broker_address", "underwriter_name",
        "underwriter_contact", "state_filings", "signature_requirements"
    ],
    "do": [
        "named_insured", "parent_organization", "subsidiaries", "policy_number",
        "carrier", "effective_date", "expiration_date", "retroactive_date",
        "claims_made_indicator", "pending_litigation", "prior_acts_coverage",
        "discovery_period", "continuity_date", "limit_of_liability", "aggregate_limit",
        "retention_amount", "side_a_coverage", "side_b_coverage", "side_c_coverage",
        "employment_practices_liability", "fiduciary_liability", "cyber_endorsement",
        "regulatory_coverage", "defense_outside_limits", "advancement_of_defense_costs",
        "allocation_clause", "severability_clause", "insured_persons_definition",
        "organization_definition", "financial_statements_attached", "revenue",
        "net_income", "total_assets", "market_capitalization", "number_of_employees",
        "number_of_directors", "public_private_status", "bankruptcy_history",
        "mergers_acquisitions", "prior_claims", "sec_investigations", "internal_investigations",
        "regulatory_actions", "antitrust_claims", "pollution_exclusion", "bodily_injury_exclusion",
        "professional_services_exclusion", "insured_vs_insured_exclusion", "contract_exclusion",
        "major_shareholders", "ownership_percentage", "foreign_operations", "adr_coverage",
        "epl_sublimit", "fiduciary_sublimit", "runoff_coverage", "extended_reporting_period",
        "premium_amount", "terrorism_coverage", "coverage_territory", "defense_counsel_provisions",
        "arbitration_clause", "choice_of_law", "cancellation_terms", "non_renewal_terms",
        "broker_information", "underwriter_information", "endorsements", "supplemental_forms",
        "signature_section", "warranty_statement", "application_date"
    ],
    "cyber": [
        "named_insured", "policy_number", "carrier", "effective_date", "expiration_date",
        "retroactive_date", "limit_of_liability", "retention", "privacy_liability",
        "network_security_liability", "media_liability", "regulatory_defense", "pci_coverage",
        "cyber_extortion", "data_breach_response", "crisis_management", "business_interruption",
        "dependent_business_interruption", "digital_asset_restoration", "social_engineering_fraud",
        "funds_transfer_fraud", "cyber_crime_endorsement", "number_of_records", "annual_revenue",
        "industry_type", "security_controls", "mfa_implemented", "encryption_practices",
        "prior_incidents", "premium", "endorsements"
    ],
    "gl": [
        "named_insured", "mailing_address", "policy_number", "carrier", "effective_date",
        "expiration_date", "general_aggregate_limit", "products_completed_operations_aggregate",
        "personal_and_advertising_injury", "each_occurrence_limit", "damage_to_rented_premises",
        "medical_expense_limit", "deductible", "self_insured_retention", "coverage_form",
        "claims_made_indicator", "retroactive_date", "additional_insureds", "waiver_of_subrogation",
        "primary_non_contributory_wording", "classification_codes", "business_description",
        "annual_payroll", "annual_sales", "number_of_employees", "locations_covered",
        "products_liability_included", "liquor_liability_included", "hired_non_owned_auto",
        "stop_gap_coverage", "terrorism_coverage", "prior_claims", "premium", "endorsements",
        "supplemental_schedules", "broker_information"
    ],
    "property": [
        "named_insured", "property_address", "policy_number", "carrier", "effective_date",
        "expiration_date", "building_limit", "business_personal_property_limit", "business_income_limit",
        "extra_expense_limit", "equipment_breakdown", "ordinance_or_law_coverage", "flood_coverage",
        "earthquake_coverage", "windstorm_coverage", "named_storm_coverage", "blanket_coverage",
        "coinsurance_percentage", "valuation_method", "replacement_cost", "actual_cash_value",
        "deductible", "wind_deductible", "flood_deductible", "earthquake_deductible",
        "number_of_buildings", "construction_type", "occupancy_type", "protection_class",
        "year_built", "square_footage", "sprinklered_status", "alarm_system", "roof_type",
        "roof_age", "electrical_updates", "plumbing_updates", "hvac_updates", "fire_extinguishers",
        "fire_alarms", "burglar_alarms", "distance_to_hydrant", "distance_to_fire_station",
        "business_interruption_period", "waiting_period", "tenant_improvements", "outdoor_signs",
        "valuable_papers", "accounts_receivable", "fine_arts_coverage", "computer_equipment",
        "mobile_equipment", "spoilage_coverage", "utility_interruption", "service_interruption",
        "leasehold_interest", "vacancy_percentage", "mortgage_holder", "loss_payee", "prior_losses",
        "premium", "forms", "endorsements", "inspection_requirements", "broker_information",
        "underwriter_information"
    ],
    "commercial-umbrella": [
        "named_insured", "policy_number", "carrier", "effective_date", "expiration_date",
        "umbrella_limit", "excess_limit", "self_insured_retention", "underlying_general_liability",
        "underlying_auto_liability", "underlying_employers_liability", "underlying_coverage_schedule",
        "follow_form_indicator", "drop_down_coverage", "defense_outside_limits", "retained_limit",
        "coverage_territory", "products_liability_included", "liquor_liability_included",
        "professional_liability_exclusion", "aircraft_exclusion", "watercraft_exclusion",
        "prior_claims", "premium", "endorsements", "supplemental_forms", "broker_information"
    ],
    "workers-comp": [
        "named_insured", "policy_number", "carrier", "effective_date", "expiration_date",
        "states_covered", "class_codes", "estimated_annual_payroll", "number_of_employees",
        "experience_modification_rate", "employers_liability_limit", "bodily_injury_by_accident",
        "bodily_injury_by_disease_policy_limit", "bodily_injury_by_disease_each_employee",
        "voluntary_compensation", "waiver_of_subrogation", "owner_officer_inclusion",
        "sole_proprietor_inclusion", "safety_program", "prior_losses", "premium",
        "terrorism_coverage", "endorsements"
    ]
}


def _build_comparison_prompt(
    summary_a: AcordFormSummary,
    summary_b: AcordFormSummary,
    name_a: str,
    name_b: str,
    deviation_threshold_percent: int,
    lob: Optional[str] = None,
) -> str:
    import json as _json

    def _as_dict(s: AcordFormSummary) -> dict:
        d = s.model_dump(mode="json", exclude_none=True)
        d.pop("raw_text", None)
        return d

    fields_a = _json.dumps(_as_dict(summary_a), indent=2)[:6000]
    fields_b = _json.dumps(_as_dict(summary_b), indent=2)[:6000]
    raw_a = (summary_a.raw_text or "")[:6000]
    raw_b = (summary_b.raw_text or "")[:6000]

    lob_section = ""
    lob_key = (lob or "").lower().strip()
    if lob_key in _LOB_FIELDS:
        field_list = "\n".join(f"  - {f}" for f in _LOB_FIELDS[lob_key])
        field_count = len(_LOB_FIELDS[lob_key])
        lob_section = (
            f"\nLine of Business: {lob_key} ({field_count} workbook fields)\n"
            f"You MUST extract and compare ALL of the following {field_count} fields for both policies.\n"
            f"Set the value to null if a field is not present in the document.\n"
            f"Fields to compare:\n{field_list}\n"
            f"Include every field above as a key in extracted_fields.policyA and extracted_fields.policyB.\n"
        )

    return (
        "You are a policy checking engine for insurance documents.\n"
        "Compare two policy documents and produce a STRICT JSON object only (no markdown, no prose outside JSON).\n\n"
        "Rules:\n"
        f"- Compute deviation_percent (0..100): % of materially changed coverage/clauses vs the combined set.\n"
        f"- Set deviation_exceeds_threshold = deviation_percent > {deviation_threshold_percent}.\n"
        "- If deviation_exceeds_threshold is true, include recommendation with recommended_policy (A|B|NEITHER) and a short rationale list.\n"
        "- Always include clause_diff.clauses with status=added|removed|changed and before/after text.\n"
        "- Always include extracted_fields.policyA and extracted_fields.policyB with key fields (carrier, premiums, limits, deductibles, effective dates, exclusions, endorsements).\n"
        "- Include taxonomy fields (domain, doc_type_a, doc_type_b, lines_of_business).\n"
        "- If data is missing, use null and add a warning to the warnings array.\n"
        f"{lob_section}\n"
        "Output JSON schema:\n"
        "{\n"
        '  "taxonomy": {"domain": "insurance", "doc_type_a": string, "doc_type_b": string, "lines_of_business": string[]},\n'
        '  "extracted_fields": {"policyA": object, "policyB": object},\n'
        '  "clause_diff": {"clauses": [{"id": string, "title": string, "status": "added"|"removed"|"changed", "before": string, "after": string, "path": string}]},\n'
        '  "deviation_percent": number,\n'
        '  "deviation_exceeds_threshold": boolean,\n'
        '  "recommendation": {"recommended_policy": "A"|"B"|"NEITHER", "rationale": string[]},\n'
        '  "warnings": string[]\n'
        "}\n\n"
        f"Document A: {name_a}\n"
        f"Extracted structured fields:\n{fields_a}\n"
        f"Raw text context:\n{raw_a}\n\n"
        f"Document B: {name_b}\n"
        f"Extracted structured fields:\n{fields_b}\n"
        f"Raw text context:\n{raw_b}\n"
    )


async def _compare_via_llm(prompt: str) -> dict:
    import json as _json
    errors: list[str] = []

    def _parse(content: str) -> dict:
        c = content.strip()
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", c, re.DOTALL)
        c = m.group(1).strip() if m else c
        first = c.find("{")
        last = c.rfind("}")
        if first != -1 and last > first:
            c = c[first: last + 1]
        try:
            return _json.loads(c)
        except _json.JSONDecodeError:
            repaired = re.sub(r",\s*([}\]])", r"\1", c)
            return _json.loads(repaired)

    def _runpod_auth_headers(token: str) -> dict:
        tok = token[7:].strip() if token.lower().startswith("bearer ") else token
        return {
            "Authorization": f"Bearer {tok}",
            "x-api-key": tok,
            "Content-Type": "application/json",
        }

    def _extract_text(data: dict) -> str:
        text = (
            data.get("text")
            or data.get("generated_text")
            or data.get("response")
            or data.get("output")
            or ""
        )
        if isinstance(text, list):
            text = text[0] if text else ""
        return str(text).strip()

    runpod_token = (FIDEON_SECRET_KEY or RUNPOD_API_KEY).strip()
    if RUNPOD_GENERATE_URL:
        try:
            async with httpx.AsyncClient(timeout=300) as slm_client:
                for body in [
                    {
                        "prompt":         prompt,
                        "model":          RUNPOD_MODEL_LLAMA,
                        "max_new_tokens": 4096,
                        "temperature":    0.1,
                        "raw":            True,
                    },
                    {
                        "prompt":         prompt,
                        "max_new_tokens": 4096,
                        "temperature":    0.1,
                    },
                ]:
                    headers = _runpod_auth_headers(runpod_token) if runpod_token else {"Content-Type": "application/json"}
                    resp = await slm_client.post(RUNPOD_GENERATE_URL, json=body, headers=headers)
                    if resp.is_success:
                        text = _extract_text(resp.json())
                        if text:
                            return _parse(text)
                    else:
                        errors.append(f"RunPod SLM {resp.status_code}: {resp.text[:200]}")
                        break
        except Exception as exc:
            errors.append(f"RunPod SLM error: {exc}")

    messages = [
        {"role": "system", "content": "You are a strict JSON generator. Output ONLY valid JSON matching the requested schema."},
        {"role": "user", "content": prompt},
    ]
    payload = {"messages": messages, "max_tokens": 4096, "stream": False}

    async with httpx.AsyncClient(timeout=180) as client:
        if GROQ_API_KEY and GROQ_OPENAI_COMPAT_URL:
            try:
                resp = await client.post(
                    GROQ_OPENAI_COMPAT_URL,
                    json={**payload, "model": GROQ_MODEL_CHAT},
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                )
                if resp.is_success:
                    content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    return _parse(content)
                errors.append(f"Groq {resp.status_code}: {resp.text[:200]}")
            except Exception as exc:
                errors.append(f"Groq error: {exc}")

        if OPENAI_API_KEY:
            try:
                resp = await client.post(
                    OPENAI_CHAT_COMPLETIONS_URL,
                    json={**payload, "model": OPENAI_MODEL},
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                )
                if resp.is_success:
                    content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    return _parse(content)
                errors.append(f"OpenAI {resp.status_code}: {resp.text[:200]}")
            except Exception as exc:
                errors.append(f"OpenAI error: {exc}")

    raise RuntimeError(f"All LLM providers failed for comparison: {'; '.join(errors)}")


@router.post("/compare")
async def compare_policies(
    file_a: UploadFile = File(..., description="First policy document (PDF or text)"),
    file_b: UploadFile = File(..., description="Second policy document (PDF or text)"),
    authorization: str | None = Header(default=None),
    deviation_threshold_percent: int = Query(default=10, ge=0, le=100),
    lob: Optional[str] = Query(default=None, description="Line of business slug, e.g. 'commercial-auto'"),
):
    """
    Extract both policy documents using the ACORD Form Understanding pipeline,
    and compare them field-by-field using LOB-specific reasoning.
    Returns a PolicyComparisonStructured JSON object.
    """
    user = await verify_user(authorization)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info(
        "PolicyComparison[compare] request: file_a=%s file_b=%s threshold=%s lob=%s user_id=%s",
        file_a.filename, file_b.filename, deviation_threshold_percent, lob, user_id,
    )

    logger.info("[SYSTEM] Initializing extraction pipeline for %s...", lob)
    logger.info("[OCR] Parsing PDF layouts and tables...")

    await _ensure_runpod_ready_for_acord()

    try:
        logger.info("[EXTRACTION] Sourcing keys from %s and %s...", file_a.filename, file_b.filename)
        summary_a, summary_b = await asyncio.gather(
            _extract_summary_from_file(file_a),
            _extract_summary_from_file(file_b),
        )
    except Exception as exc:
        logger.exception("PolicyComparison[compare] extraction failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"Document extraction failed: {exc}") from exc

    logger.info("[TAXONOMY] Classifying forms as %s...", lob)
    name_a = file_a.filename or "Policy A"
    name_b = file_b.filename or "Policy B"
    prompt = _build_comparison_prompt(
        summary_a, summary_b, name_a, name_b, deviation_threshold_percent, lob=lob
    )

    try:
        logger.info("[DIFF] Computing limits and deductible deltas...")
        logger.info("[SCORING] Evaluating material coverage changes...")
        result = await _compare_via_llm(prompt)
    except Exception as exc:
        logger.exception("PolicyComparison[compare] LLM call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"LLM comparison failed: {exc}") from exc

    logger.info("[REPORT] Formatting final JSON response...")
    logger.info("[SUCCESS] Comparison workflow complete.")
    logger.info("PolicyComparison[compare] done: file_a=%s file_b=%s lob=%s user_id=%s", name_a, name_b, lob, user_id)
    return result
