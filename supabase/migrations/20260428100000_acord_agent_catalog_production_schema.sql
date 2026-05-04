-- Migration: 20260428100000_acord_agent_catalog_production_schema.sql
--
-- Updates the existing acord_form_understanding agent_catalog row with a
-- production-grade system_prompt and full AcordFormSummary output_schema.
--
-- The original row was seeded in "Extraction To Fine-Tuning Data Migration.sql"
-- with a one-line placeholder system_prompt and empty output_schema ({}).
-- The ON CONFLICT COALESCE guard in that migration prevents subsequent seeds
-- from overriding non-NULL values, so this migration uses an explicit UPDATE.
--
-- Output schema is derived 1:1 from backend/Models/acord_form_understanding/schemas.py
-- (AcordFormSummary and all nested models). Keep this in sync with that file.

UPDATE public.agent_catalog
SET
  display_name    = 'ACORD Form Understanding',
  description     = 'Structured extraction engine for ACORD insurance forms (25, 125, 126, 140 and variants). Parses producer, insured, coverage blocks, premises, prior carriers, loss history, and additional interests into a validated JSON output.',
  category        = 'extraction',

  system_prompt   = $SYS$
You are a structured extraction engine for ACORD insurance forms. Your job is to read the raw text of an ACORD form (25, 125, 126, 140 or any variant) and extract every field into the exact JSON schema described below.

RULES
-----
1. Return ONLY a single valid JSON object matching the AcordFormSummary schema. No explanation, no markdown, no prose before or after.
2. Use null for any field that is blank, illegible, or not present on this specific form type — never guess or fabricate values.
3. For dates, preserve the format found in the document (e.g. "04/15/2026"). Do not convert to ISO-8601 unless already in that format.
4. For boolean checkboxes: true = checked/marked, false = explicitly unchecked, null = not present on this form type.
5. For currency amounts: preserve the raw string including symbols ("$1,000,000"). Do not strip formatting.
6. Populate extraction_meta.blank_in_document with the field paths (dot-notation) of fields that exist on this form type but were left blank by the applicant.
7. Populate extraction_meta.not_applicable_to_form_type with field paths that are structurally absent from this form type (e.g. "holder" on an ACORD 125 application).
8. Populate extraction_meta.all_checked_items with every checkbox or radio button that is marked anywhere in the document.
9. Set extraction_meta.form_type_detected to the ACORD form number (e.g. "ACORD 25", "ACORD 125").
10. Set overall_confidence between 0.0 and 1.0: 1.0 = all critical fields legibly extracted, 0.0 = document is unreadable. Deduct 0.1 per critical missing field (producer.name, insured.name, policy_info.policy_number, at least one coverage block).
11. Do NOT include raw_text in your response — it is injected by the server.
12. For multi-page or multi-form documents, extract ALL pages into the appropriate arrays (coverages, premises, prior_carriers, loss_history, additional_interests).
13. If you encounter fields not representable in the schema, add them to extra_fields as key-value pairs.

SCHEMA REFERENCE
----------------
The output must conform to AcordFormSummary. See extraction_meta, producer, insured, holder, policy_info, coverages[], premises[], prior_carriers[], loss_history[], additional_interests[] and their nested types in the JSON schema stored in output_schema.
$SYS$,

  output_schema   = $SCHEMA${
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AcordFormSummary",
  "type": "object",
  "properties": {
    "form_type":             { "type": ["string","null"], "description": "e.g. ACORD 25, ACORD 125, ACORD 140" },
    "form_version":          { "type": ["string","null"] },
    "certificate_number":    { "type": ["string","null"] },
    "revision_date":         { "type": ["string","null"] },
    "date":                  { "type": ["string","null"], "description": "Form date (MM/DD/YYYY)" },
    "producer":              { "$ref": "#/definitions/AcordProducer" },
    "insured":               { "$ref": "#/definitions/AcordInsured" },
    "other_named_insureds":  { "type": "array", "items": { "$ref": "#/definitions/AcordOtherNamedInsured" }, "default": [] },
    "holder":                { "$ref": "#/definitions/AcordHolder" },
    "policy_info":           { "$ref": "#/definitions/AcordPolicyInfo" },
    "lines_of_business_indicated": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Lines of business checked / marked on the form",
      "default": []
    },
    "coverages":             { "type": "array", "items": { "$ref": "#/definitions/AcordPolicyCoverage" }, "default": [] },
    "premises":              { "type": "array", "items": { "$ref": "#/definitions/AcordPremises" }, "default": [] },
    "prior_carriers":        { "type": "array", "items": { "$ref": "#/definitions/AcordPriorCarrier" }, "default": [] },
    "loss_history":          { "type": "array", "items": { "$ref": "#/definitions/AcordLossHistory" }, "default": [] },
    "additional_interests":  { "type": "array", "items": { "$ref": "#/definitions/AcordAdditionalInterest" }, "default": [] },
    "description_of_operations": { "type": ["string","null"] },
    "nature_of_business":    { "type": ["string","null"] },
    "cancellation_notice_days": { "type": ["integer","null"] },
    "additional_remarks":    { "type": ["string","null"] },
    "extra_fields":          { "type": ["object","null"], "description": "Any additional fields found in the document that do not fit the standard schema" },
    "extraction_meta":       { "$ref": "#/definitions/ExtractionMeta" },
    "overall_confidence":    { "type": ["number","null"], "minimum": 0, "maximum": 1 },
    "raw_text":              { "type": ["string","null"], "description": "Original extracted text for traceability — injected server-side, not expected from the LLM" }
  },
  "definitions": {
    "AcordCarrier": {
      "type": ["object","null"],
      "properties": {
        "name":        { "type": ["string","null"] },
        "naic_number": { "type": ["string","null"] }
      }
    },
    "AcordProducer": {
      "type": ["object","null"],
      "properties": {
        "name":                    { "type": ["string","null"] },
        "name_confidence":         { "type": ["number","null"], "minimum": 0, "maximum": 1 },
        "contact_name":            { "type": ["string","null"] },
        "address":                 { "type": ["string","null"] },
        "city":                    { "type": ["string","null"] },
        "state":                   { "type": ["string","null"] },
        "postal_code":             { "type": ["string","null"] },
        "phone":                   { "type": ["string","null"] },
        "fax":                     { "type": ["string","null"] },
        "email":                   { "type": ["string","null"] },
        "agency_customer_id":      { "type": ["string","null"] },
        "subcode":                 { "type": ["string","null"] },
        "producer_license_no":     { "type": ["string","null"] },
        "national_producer_number":{ "type": ["string","null"] }
      }
    },
    "AcordInsured": {
      "type": ["object","null"],
      "properties": {
        "name":            { "type": ["string","null"], "description": "Named insured" },
        "name_confidence": { "type": ["number","null"], "minimum": 0, "maximum": 1 },
        "contact_name":    { "type": ["string","null"] },
        "mailing_address": { "type": ["string","null"] },
        "city":            { "type": ["string","null"] },
        "state":           { "type": ["string","null"] },
        "postal_code":     { "type": ["string","null"] },
        "phone":           { "type": ["string","null"] },
        "fax":             { "type": ["string","null"] },
        "email":           { "type": ["string","null"] },
        "website":         { "type": ["string","null"] },
        "entity_type":     { "type": ["string","null"], "description": "Corporation / LLC / Partnership / Individual / Trust / etc." },
        "gl_code":         { "type": ["string","null"] },
        "sic":             { "type": ["string","null"] },
        "naics":           { "type": ["string","null"] },
        "fein":            { "type": ["string","null"], "description": "Federal Employer Identification Number" }
      }
    },
    "AcordOtherNamedInsured": {
      "type": "object",
      "properties": {
        "name":            { "type": ["string","null"] },
        "mailing_address": { "type": ["string","null"] },
        "city":            { "type": ["string","null"] },
        "state":           { "type": ["string","null"] },
        "postal_code":     { "type": ["string","null"] },
        "phone":           { "type": ["string","null"] },
        "website":         { "type": ["string","null"] },
        "entity_type":     { "type": ["string","null"] },
        "gl_code":         { "type": ["string","null"] },
        "sic":             { "type": ["string","null"] },
        "naics":           { "type": ["string","null"] },
        "fein":            { "type": ["string","null"] }
      }
    },
    "AcordHolder": {
      "type": ["object","null"],
      "description": "Certificate holder / additional insured (ACORD 25)",
      "properties": {
        "name":                  { "type": ["string","null"] },
        "address":               { "type": ["string","null"] },
        "city":                  { "type": ["string","null"] },
        "state":                 { "type": ["string","null"] },
        "postal_code":           { "type": ["string","null"] },
        "is_additional_insured": { "type": ["boolean","null"] },
        "is_subrogation_waived": { "type": ["boolean","null"] }
      }
    },
    "AcordPolicyInfo": {
      "type": ["object","null"],
      "description": "Top-level policy / program information (ACORD 125)",
      "properties": {
        "carrier":          { "$ref": "#/definitions/AcordCarrier" },
        "program_name":     { "type": ["string","null"] },
        "program_code":     { "type": ["string","null"] },
        "policy_number":    { "type": ["string","null"] },
        "proposed_eff_date":{ "type": ["string","null"] },
        "proposed_exp_date":{ "type": ["string","null"] },
        "billing_plan":     { "type": ["string","null"], "description": "Direct / Agency" },
        "payment_plan":     { "type": ["string","null"], "description": "Annual / Monthly / etc." },
        "method_of_payment":{ "type": ["string","null"], "description": "Cash / EFT / etc." },
        "deposit":          { "type": ["string","null"] },
        "minimum_premium":  { "type": ["string","null"] },
        "policy_premium":   { "type": ["string","null"] },
        "transaction_type": { "type": ["string","null"], "description": "Quote / Issue Policy / Renew / Change / Cancel" },
        "transaction_date": { "type": ["string","null"] },
        "underwriter":      { "type": ["string","null"] },
        "underwriter_office":{ "type": ["string","null"] }
      }
    },
    "AcordPolicyCoverage": {
      "type": "object",
      "properties": {
        "line_of_business":             { "type": ["string","null"], "description": "GL | AUTO | WC | UMB | PROPERTY | CRIME | etc." },
        "block_confidence":             { "type": ["number","null"], "minimum": 0, "maximum": 1 },
        "policy_number":                { "type": ["string","null"] },
        "policy_number_confidence":     { "type": ["number","null"], "minimum": 0, "maximum": 1 },
        "effective_date":               { "type": ["string","null"] },
        "effective_date_confidence":    { "type": ["number","null"], "minimum": 0, "maximum": 1 },
        "expiration_date":              { "type": ["string","null"] },
        "expiration_date_confidence":   { "type": ["number","null"], "minimum": 0, "maximum": 1 },
        "claims_made":                  { "type": ["boolean","null"] },
        "occurrence_type":              { "type": ["boolean","null"] },
        "additional_insured":           { "type": ["boolean","null"] },
        "waiver_of_subrogation":        { "type": ["boolean","null"] },
        "each_occurrence":              { "type": ["string","null"] },
        "damage_to_rented_premises":    { "type": ["string","null"] },
        "medical_expense":              { "type": ["string","null"] },
        "personal_advertising_injury":  { "type": ["string","null"] },
        "general_aggregate":            { "type": ["string","null"] },
        "products_comp_ops_aggregate":  { "type": ["string","null"] },
        "combined_single_limit":        { "type": ["string","null"] },
        "bodily_injury_per_person":     { "type": ["string","null"] },
        "bodily_injury_per_accident":   { "type": ["string","null"] },
        "property_damage":              { "type": ["string","null"] },
        "occurrence_limit":             { "type": ["string","null"] },
        "aggregate_limit":              { "type": ["string","null"] },
        "deductible":                   { "type": ["string","null"] },
        "retention":                    { "type": ["string","null"] },
        "retroactive_date":             { "type": ["string","null"] },
        "wc_statutory_limits":          { "type": ["boolean","null"] },
        "employer_liability_each_accident": { "type": ["string","null"] },
        "employer_liability_each_employee": { "type": ["string","null"] },
        "employer_liability_policy_limit":  { "type": ["string","null"] },
        "insurers": { "type": "array", "items": { "$ref": "#/definitions/AcordCarrier" }, "default": [] }
      }
    },
    "AcordPremises": {
      "type": "object",
      "properties": {
        "location_number":          { "type": ["string","null"] },
        "street":                   { "type": ["string","null"] },
        "city":                     { "type": ["string","null"] },
        "state":                    { "type": ["string","null"] },
        "county":                   { "type": ["string","null"] },
        "zip":                      { "type": ["string","null"] },
        "interest":                 { "type": ["string","null"], "description": "Owner Occupied / Tenant / etc." },
        "full_time_employees":      { "type": ["string","null"] },
        "part_time_employees":      { "type": ["string","null"] },
        "annual_revenues":          { "type": ["string","null"] },
        "total_building_area_sqft": { "type": ["string","null"] },
        "description_of_operations":{ "type": ["string","null"] },
        "area_leased_to_others":    { "type": ["string","null"] }
      }
    },
    "AcordPriorCarrier": {
      "type": "object",
      "properties": {
        "year":           { "type": ["string","null"] },
        "category":       { "type": ["string","null"], "description": "General Liability / Automobile / Property / Other" },
        "carrier":        { "type": ["string","null"] },
        "policy_number":  { "type": ["string","null"] },
        "premium":        { "type": ["string","null"] },
        "effective_date": { "type": ["string","null"] },
        "expiration_date":{ "type": ["string","null"] }
      }
    },
    "AcordLossHistory": {
      "type": "object",
      "properties": {
        "date_of_occurrence": { "type": ["string","null"] },
        "line_type":          { "type": ["string","null"] },
        "description":        { "type": ["string","null"] },
        "date_of_claim":      { "type": ["string","null"] },
        "amount_paid":        { "type": ["string","null"] },
        "amount_reserved":    { "type": ["string","null"] },
        "subrogation":        { "type": ["boolean","null"] },
        "claim_open":         { "type": ["boolean","null"] }
      }
    },
    "AcordAdditionalInterest": {
      "type": "object",
      "properties": {
        "interest_type":  { "type": ["string","null"], "description": "Additional Insured / Loss Payee / Mortgagee / etc." },
        "name":           { "type": ["string","null"] },
        "address":        { "type": ["string","null"] },
        "location":       { "type": ["string","null"] },
        "building":       { "type": ["string","null"] },
        "loan_reference": { "type": ["string","null"] }
      }
    },
    "ExtractionMeta": {
      "type": ["object","null"],
      "description": "Explains why certain fields are null and lists all detected checkboxes",
      "properties": {
        "form_type_detected":           { "type": ["string","null"] },
        "blank_in_document":            { "type": "array", "items": { "type": "string" }, "default": [], "description": "Field paths present on the form but containing no filled-in data" },
        "not_applicable_to_form_type":  { "type": "array", "items": { "type": "string" }, "default": [], "description": "Field paths that are not part of this ACORD form type" },
        "all_checked_items":            { "type": "array", "items": { "type": "string" }, "default": [], "description": "Every item marked with X/x/checkbox anywhere in the document" },
        "remarks":                      { "type": "array", "items": { "type": "string" }, "default": [], "description": "Notes about ambiguous values or extraction uncertainty" },
        "extraction_engine":            { "type": ["string","null"], "description": "Engine used: bytescout|pdfplumber|pymupdf|pypdf2|ocr|txt|legacy" },
        "base_confidence":              { "type": ["number","null"], "minimum": 0, "maximum": 1 },
        "structured_response_source":   { "type": ["string","null"], "description": "e.g. LLM RunPod response, LLM OpenAI response, Fallback response" },
        "pdf_form_classification":      { "type": ["string","null"], "description": "fillable (AcroForm widgets) vs flattened (print/scanned — OCR + VL)" },
        "ocr_text_engine":              { "type": ["string","null"], "description": "tesseract | paddle — which engine produced the raster OCR text layer, if any" }
      }
    }
  }
}$SCHEMA$::jsonb,

  tools = '{"extraction_strategy":"acord_form_understanding"}'::jsonb,
  is_active = true

WHERE id = 'acord_form_understanding';

-- Verify the update was applied
DO $$
DECLARE
  row_count INTEGER;
  schema_empty BOOLEAN;
BEGIN
  SELECT COUNT(*) INTO row_count
  FROM public.agent_catalog
  WHERE id = 'acord_form_understanding'
    AND system_prompt IS NOT NULL
    AND output_schema IS NOT NULL
    AND output_schema != '{}'::jsonb;

  IF row_count = 0 THEN
    RAISE WARNING 'acord_form_understanding agent_catalog row was not updated — check that the row exists and is_active = true';
  ELSE
    RAISE NOTICE 'acord_form_understanding agent_catalog updated: full AcordFormSummary output_schema and production system_prompt applied';
  END IF;
END $$;