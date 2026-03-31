from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Extraction metadata ───────────────────────────────────────────────────────

class ExtractionMeta(BaseModel):
    """
    Explains WHY certain fields are null — critical for production debugging
    and user-facing transparency.
    """
    form_type_detected: Optional[str] = None
    # Fields that are null because the section/label exists but was left blank
    blank_in_document: List[str] = Field(
        default_factory=list,
        description="Field paths present on the form but containing no filled-in data",
    )
    # Fields that are null because they do not exist on this form type at all
    not_applicable_to_form_type: List[str] = Field(
        default_factory=list,
        description="Field paths that are not part of this ACORD form type",
    )
    # All checkbox/marked items found anywhere in the document
    all_checked_items: List[str] = Field(
        default_factory=list,
        description="Every item marked with X/x/checkbox anywhere in the document",
    )
    # LLM remarks about ambiguous or low-confidence values
    remarks: List[str] = Field(
        default_factory=list,
        description="Notes about ambiguous values or extraction uncertainty",
    )
    # Which PDF/text engine successfully extracted the document content
    extraction_engine: Optional[str] = Field(
        default=None,
        description="Engine used: bytescout|pdfplumber|pymupdf|pypdf2|ocr|txt|legacy",
    )
    # Base confidence used for this extraction (derived from engine)
    base_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    # Where structured fields came from: RunPod LLM vs heuristic/legacy fallback (see extraction_pipeline)
    structured_response_source: Optional[str] = Field(
        default=None,
        description="e.g. 'LLM RunPod response', 'LLM OpenAI response', 'Fallback response'",
    )
    pdf_form_classification: Optional[str] = Field(
        default=None,
        description="fillable (AcroForm widgets) vs flattened (print/scanned — OCR + VL)",
    )
    ocr_text_engine: Optional[str] = Field(
        default=None,
        description="tesseract | paddle — which engine produced the raster OCR text layer, if any",
    )


# ── Shared building blocks ────────────────────────────────────────────────────

class AcordCarrier(BaseModel):
    name: Optional[str] = None
    naic_number: Optional[str] = None


class AcordInsured(BaseModel):
    """Primary / first named insured."""
    name: Optional[str] = Field(None, description="Named insured")
    name_confidence: Optional[float] = Field(None, ge=0, le=1)
    contact_name: Optional[str] = None
    mailing_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    entity_type: Optional[str] = Field(None, description="Corporation / LLC / Partnership / Individual / Trust / etc.")
    gl_code: Optional[str] = None
    sic: Optional[str] = None
    naics: Optional[str] = None
    fein: Optional[str] = Field(None, description="Federal Employer Identification Number")


class AcordOtherNamedInsured(BaseModel):
    """Additional named insureds (ACORD 125 page 1)."""
    name: Optional[str] = None
    mailing_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    entity_type: Optional[str] = None
    gl_code: Optional[str] = None
    sic: Optional[str] = None
    naics: Optional[str] = None
    fein: Optional[str] = None


class AcordProducer(BaseModel):
    name: Optional[str] = None
    name_confidence: Optional[float] = Field(None, ge=0, le=1)
    contact_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    agency_customer_id: Optional[str] = None
    subcode: Optional[str] = None
    producer_license_no: Optional[str] = None
    national_producer_number: Optional[str] = None


class AcordHolder(BaseModel):
    """Certificate holder / additional insured (ACORD 25)."""
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    is_additional_insured: Optional[bool] = None
    is_subrogation_waived: Optional[bool] = None


# ── Policy-level information ──────────────────────────────────────────────────

class AcordPolicyInfo(BaseModel):
    """Top-level policy / program information (ACORD 125)."""
    carrier: Optional[AcordCarrier] = None
    program_name: Optional[str] = None
    program_code: Optional[str] = None
    policy_number: Optional[str] = None
    proposed_eff_date: Optional[str] = None
    proposed_exp_date: Optional[str] = None
    billing_plan: Optional[str] = Field(None, description="Direct / Agency")
    payment_plan: Optional[str] = Field(None, description="Annual / Monthly / etc.")
    method_of_payment: Optional[str] = Field(None, description="Cash / EFT / etc.")
    deposit: Optional[str] = None
    minimum_premium: Optional[str] = None
    policy_premium: Optional[str] = None
    transaction_type: Optional[str] = Field(None, description="Quote / Issue Policy / Renew / Change / Cancel")
    transaction_date: Optional[str] = None
    underwriter: Optional[str] = None
    underwriter_office: Optional[str] = None


# ── Coverage blocks (ACORD 25 / 126 / 140 style) ─────────────────────────────

class AcordPolicyCoverage(BaseModel):
    line_of_business: Optional[str] = Field(None, description="GL | AUTO | WC | UMB | PROPERTY | CRIME | etc.")
    block_confidence: Optional[float] = Field(None, ge=0, le=1)

    policy_number: Optional[str] = None
    policy_number_confidence: Optional[float] = Field(None, ge=0, le=1)
    effective_date: Optional[date] = None
    effective_date_confidence: Optional[float] = Field(None, ge=0, le=1)
    expiration_date: Optional[date] = None
    expiration_date_confidence: Optional[float] = Field(None, ge=0, le=1)

    claims_made: Optional[bool] = None
    occurrence_type: Optional[bool] = None
    additional_insured: Optional[bool] = None
    waiver_of_subrogation: Optional[bool] = None

    # GL limits
    each_occurrence: Optional[str] = None
    damage_to_rented_premises: Optional[str] = None
    medical_expense: Optional[str] = None
    personal_advertising_injury: Optional[str] = None
    general_aggregate: Optional[str] = None
    products_comp_ops_aggregate: Optional[str] = None

    # Auto limits
    combined_single_limit: Optional[str] = None
    bodily_injury_per_person: Optional[str] = None
    bodily_injury_per_accident: Optional[str] = None
    property_damage: Optional[str] = None

    # Umbrella / Excess
    occurrence_limit: Optional[str] = None
    aggregate_limit: Optional[str] = None
    deductible: Optional[str] = None
    retention: Optional[str] = None
    retroactive_date: Optional[str] = None

    # Workers Compensation
    wc_statutory_limits: Optional[bool] = None
    employer_liability_each_accident: Optional[str] = None
    employer_liability_each_employee: Optional[str] = None
    employer_liability_policy_limit: Optional[str] = None

    insurers: List[AcordCarrier] = Field(default_factory=list)


# ── Application-specific structures (ACORD 125 / 126 / 85 / 90) ──────────────

class AcordPremises(BaseModel):
    location_number: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    zip: Optional[str] = None
    interest: Optional[str] = Field(None, description="Owner Occupied / Tenant / etc.")
    full_time_employees: Optional[str] = None
    part_time_employees: Optional[str] = None
    annual_revenues: Optional[str] = None
    total_building_area_sqft: Optional[str] = None
    description_of_operations: Optional[str] = None
    area_leased_to_others: Optional[str] = None


class AcordPriorCarrier(BaseModel):
    year: Optional[str] = None
    category: Optional[str] = Field(None, description="General Liability / Automobile / Property / Other")
    carrier: Optional[str] = None
    policy_number: Optional[str] = None
    premium: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None


class AcordLossHistory(BaseModel):
    date_of_occurrence: Optional[str] = None
    line_type: Optional[str] = None
    description: Optional[str] = None
    date_of_claim: Optional[str] = None
    amount_paid: Optional[str] = None
    amount_reserved: Optional[str] = None
    subrogation: Optional[bool] = None
    claim_open: Optional[bool] = None


class AcordAdditionalInterest(BaseModel):
    interest_type: Optional[str] = Field(None, description="Additional Insured / Loss Payee / Mortgagee / etc.")
    name: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    building: Optional[str] = None
    loan_reference: Optional[str] = None


# ── Master summary ────────────────────────────────────────────────────────────

class AcordFormSummary(BaseModel):
    form_type: Optional[str] = Field(None, description="e.g. ACORD 25, ACORD 125, ACORD 140")
    form_version: Optional[str] = None
    certificate_number: Optional[str] = None
    revision_date: Optional[str] = None
    date: Optional[str] = Field(None, description="Form date (MM/DD/YYYY)")

    producer: Optional[AcordProducer] = None
    insured: Optional[AcordInsured] = None
    other_named_insureds: List[AcordOtherNamedInsured] = Field(
        default_factory=list,
        description="Additional named insureds beyond the first",
    )
    holder: Optional[AcordHolder] = None

    # Application-level policy info (ACORD 125)
    policy_info: Optional[AcordPolicyInfo] = None

    # Lines of business selected / indicated on the form
    lines_of_business_indicated: List[str] = Field(
        default_factory=list,
        description="Lines of business checked / marked on the form, e.g. ['BUSINESS OWNERS', 'TRUCKERS', 'COMMERCIAL GENERAL LIABILITY']",
    )

    # Certificate-style coverage blocks (ACORD 25 / 126)
    coverages: List[AcordPolicyCoverage] = Field(default_factory=list)

    # Premises
    premises: List[AcordPremises] = Field(default_factory=list)

    # Prior carrier history
    prior_carriers: List[AcordPriorCarrier] = Field(default_factory=list)

    # Loss history
    loss_history: List[AcordLossHistory] = Field(default_factory=list)

    # Additional interests
    additional_interests: List[AcordAdditionalInterest] = Field(default_factory=list)

    description_of_operations: Optional[str] = Field(
        None, description="Description of operations / locations / vehicles / special items"
    )
    nature_of_business: Optional[str] = None
    cancellation_notice_days: Optional[int] = None
    additional_remarks: Optional[str] = None

    # Catch-all: any fields extracted by the LLM that don't fit above slots
    extra_fields: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Any additional fields found in the document that don't fit the standard schema",
    )

    # Production-grade extraction transparency
    extraction_meta: Optional[ExtractionMeta] = Field(
        default=None,
        description="Explains why certain fields are null and lists all detected checkboxes",
    )

    overall_confidence: Optional[float] = Field(None, ge=0, le=1)
    raw_text: Optional[str] = Field(None, description="Original extracted text for traceability")
