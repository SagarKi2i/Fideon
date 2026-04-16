# NeuraBOX Insurance Pods — Reference Documentation

> **Scope**: FNOL (Claims Intelligence), Quote Generation, Policy Comparison, ACORD Form Extraction  
> **Last updated**: 2026-04-15

---

## Table of Contents

1. [Pod Architecture Overview](#pod-architecture-overview)
2. [Shared Database Schema](#shared-database-schema)
3. [Shared API Reference](#shared-api-reference)
4. [Pod 1 — FNOL (Claims Intelligence)](#pod-1--fnol-claims-intelligence)
5. [Pod 2 — Quote Generation](#pod-2--quote-generation)
6. [Pod 3 — Policy Comparison](#pod-3--policy-comparison)
7. [Pod 4 — ACORD Form Extraction](#pod-4--acord-form-extraction)
8. [Confidence & Training Workflow](#confidence--training-workflow)
9. [Environment Variables](#environment-variables)

---

## Pod Architecture Overview

All four pods share the same **generic pod framework**. Each pod is identified by a `pod_id` string and plugs into the same extraction → feedback → admin-review → fine-tuning pipeline.

```
User uploads document / provides input
        │
        ▼
POST /api/pods/{pod_id}/extract
        │
        ▼
Pod-specific extractor
(LLM + heuristics + OCR)
        │
        ▼
pod_extraction_runs (status = draft)
        │
        ▼
User reviews + submits feedback
(thumbs_up/down + optional JSON corrections)
        │
        ▼
Confidence evaluation
  ┌─────────────────────────────┐
  │ confidence >= threshold     │──▶ auto-approved
  │ confidence <  threshold     │──▶ pod_admin_queue (needs_admin_review)
  └─────────────────────────────┘
        │
        ▼
Admin reviews (approve / rework / reject)
        │
        ▼
pod_training_jobs  (if AUTO_FINE_TUNE_ON_POD_APPROVAL=true)
        │
        ▼
Quality gates → model update
```

**Pack membership**

| Pack | Pods included |
|------|--------------|
| Underwriting Pack | quote-generation, policy-comparison, acord-parser (+ 12 others) |
| Claims Pack | claims-fnol (+ 4 others) |
| Distribution Pack | policy-comparison (+ 6 others) |

---

## Shared Database Schema

Migration file: `supabase/migrations/20260320120000_pod_workflow_shared_tables.sql`

All four pods persist data to these five tables. Every row carries a `pod_id` column so records from different pods are stored together but remain logically separated.

### `pod_extraction_runs`

Core record created for every extraction attempt.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `UUID` PK | Auto-generated run identifier |
| `created_at` | `TIMESTAMPTZ` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Auto-updated on every change |
| `created_by` | `UUID` FK → `auth.users` | User who triggered the extraction |
| `pod_id` | `TEXT` NOT NULL | e.g. `claims-fnol`, `quote-generation`, `policy-comparison`, `acord_form_understanding` |
| `source_filename` | `TEXT` | Original uploaded filename |
| `source_mime` | `TEXT` | MIME type of uploaded file |
| `raw_text` | `TEXT` | Raw text extracted from document |
| `extracted_json` | `JSONB` | Pod-specific structured output (see per-pod output schema) |
| `overall_confidence` | `DOUBLE PRECISION` | Model confidence score 0.0–1.0 |
| `status` | `TEXT` | `draft` → `submitted` → `needs_admin_review` → `approved` / `rejected` |

**Indexes**: `created_by`, `pod_id`, `status`, `created_at DESC`  
**RLS**: Users can read/write own rows; admins can manage all rows.

---

### `pod_extraction_feedback`

User or admin correction attached to a run.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `UUID` PK | |
| `created_at` | `TIMESTAMPTZ` | |
| `created_by` | `UUID` FK → `auth.users` | |
| `pod_id` | `TEXT` NOT NULL | Mirrors the parent run's pod_id |
| `run_id` | `UUID` FK → `pod_extraction_runs` | |
| `actor_role` | `TEXT` | `user` or `admin` |
| `thumbs_up` | `BOOLEAN` | Positive / negative validation signal |
| `notes` | `TEXT` | Free-text annotation |
| `corrected_json` | `JSONB` | Full or partial corrected output |

---

### `pod_admin_queue`

One row per run that requires admin review. Created automatically when confidence falls below threshold or when user explicitly requests review.

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | `UUID` PK FK → `pod_extraction_runs` | |
| `pod_id` | `TEXT` NOT NULL | |
| `created_at` | `TIMESTAMPTZ` | |
| `updated_at` | `TIMESTAMPTZ` | |
| `priority` | `INTEGER` | Higher = reviewed first |
| `reason` | `TEXT` | Why this run was queued |
| `assigned_to` | `UUID` FK → `auth.users` | Admin assignee |
| `state` | `TEXT` | `open` → `in_progress` → `approved` / `rework` / `rejected` |

---

### `pod_training_jobs`

One fine-tuning job per approved run (when `AUTO_FINE_TUNE_ON_POD_APPROVAL=true`).

| Column | Type | Description |
|--------|------|-------------|
| `id` | `UUID` PK | |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |
| `pod_id` | `TEXT` NOT NULL | |
| `run_id` | `UUID` FK → `pod_extraction_runs` | UNIQUE — one job per run |
| `created_by` | `UUID` FK → `auth.users` | |
| `status` | `TEXT` | `queued` → `running` → `completed` / `failed` |
| `dataset_path` | `TEXT` | Path to prepared training dataset |
| `output_dir` | `TEXT` | Where fine-tuned weights are saved |
| `log_path` | `TEXT` | Training log file |
| `error` | `TEXT` | Error message if status=failed |
| `started_at` / `finished_at` | `TIMESTAMPTZ` | |

---

### `pod_eval_results`

Evaluation metrics recorded after each training job. One row per `(job_id, eval_set)`.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `UUID` PK | |
| `created_at` | `TIMESTAMPTZ` | |
| `pod_id` | `TEXT` NOT NULL | |
| `job_id` | `UUID` FK → `pod_training_jobs` | |
| `eval_set` | `TEXT` | `seen` / `paraphrased` / `oos` / `combined` |
| `exact_match` | `DOUBLE PRECISION` | Fraction of fields with exact match |
| `soft_accuracy` | `DOUBLE PRECISION` | Near-match accuracy |
| `semantic_sim` | `DOUBLE PRECISION` | Embedding cosine similarity |
| `hallucination_rate` | `DOUBLE PRECISION` | Fraction of hallucinated fields |
| `refusal_rate` | `DOUBLE PRECISION` | Fraction of refused outputs |
| `metrics_json` | `JSONB` | Full metrics payload |
| `notes` | `TEXT` | Reviewer notes |

**Unique constraint**: `(job_id, eval_set)`

---

## Shared API Reference

Base prefix: `/api/pods/{pod_id}`  
Schema file: `backend/app/schemas/pod_workflow.py`

### User Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/{pod_id}/extract` | Submit file/text for extraction. Returns `run_id` + initial extracted JSON. |
| `GET` | `/{pod_id}/runs/{run_id}` | Retrieve a single extraction result. |
| `POST` | `/{pod_id}/runs/{run_id}/re-extract` | Re-run extraction with an optional hint. |
| `POST` | `/{pod_id}/runs/{run_id}/submit` | Submit user feedback (thumbs + corrections). |
| `GET` | `/{pod_id}/runs` | List paginated runs for the authenticated user. |

**`PodExtractResponse`**
```json
{
  "run_id": "uuid",
  "status": "draft",
  "overall_confidence": 0.92,
  "extracted": { /* pod-specific JSON */ }
}
```

**`PodSubmitRequest`**
```json
{
  "thumbs_up": true,
  "notes": "Looks correct",
  "corrected_json": { /* optional partial/full correction */ },
  "require_admin_approval_for_training": false
}
```

**`PodReExtractRequest`**
```json
{
  "extraction_hint": "Focus on the endorsement section"
}
```

### Admin Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{pod_id}/admin/queue/stats` | Queue size, state breakdown |
| `GET` | `/{pod_id}/admin/queue` | Paginated queue (filterable by state/priority) |
| `POST` | `/{pod_id}/admin/{run_id}/review` | Review a single run |
| `POST` | `/{pod_id}/admin/batch-review` | Review 1–50 runs at once |
| `GET` | `/{pod_id}/admin/queue/{run_id}/detail` | Full queue item detail |
| `PATCH` | `/{pod_id}/admin/queue/{run_id}/detail` | Update queue item (e.g. re-assign) |
| `GET` | `/{pod_id}/admin/jobs` | List training jobs |
| `GET` | `/{pod_id}/admin/jobs/by-run/{run_id}` | Job for a specific run |
| `GET` | `/{pod_id}/admin/jobs/by-run/{run_id}/history` | Job history for a run |
| `GET` | `/{pod_id}/admin/jobs/{job_id}` | Job details |
| `GET` | `/{pod_id}/admin/jobs/{job_id}/eval` | Evaluation metrics |
| `GET` | `/{pod_id}/admin/jobs/{job_id}/log` | Raw training log |
| `GET` | `/{pod_id}/admin/runs/{run_id}/health-card` | Confidence + feedback health metrics |

**`PodAdminReviewRequest`**
```json
{
  "decision": "approve",
  "notes": "All fields verified",
  "corrected_json": { /* optional */ },
  "assigned_to": "admin-user-uuid"
}
```

**`PodBatchReviewRequest`**
```json
{
  "run_ids": ["uuid-1", "uuid-2"],
  "decision": "approve",
  "notes": "Batch approval after spot-check"
}
```

---

## Pod 1 — FNOL (Claims Intelligence)

### Identity

| Field | Value |
|-------|-------|
| **Pod ID** | `claims-fnol` |
| **Category** | Claims |
| **Segment** | Broker |
| **Pack** | Claims Pack |
| **Frontend UI** | `frontend/src/components/playground/ClaimsFNOLUI.tsx` |
| **API prefix** | `/api/pods/claims-fnol` |

### Description

The FNOL pod is the first point of contact when a loss event occurs. It accepts a natural-language description of an incident plus optional supporting documents and produces a structured analysis report covering incident classification, coverage applicability, recommended next steps, and documentation requirements. The output is designed to accelerate the claims intake process for brokers and adjusters.

### Required Input

| Field | Type | Required | Details |
|-------|------|----------|---------|
| `description` | `string` (textarea) | **Yes** | Free-text description of the incident. Should include: date, location, parties involved, nature of loss, and known damages. Minimum meaningful length ~50 characters. |
| `file` | `File` (PDF / DOCX / JPG / PNG) | No | Supporting document: police report, photos, repair estimate, witness statement, etc. |

**Example payload sent to `onRun`:**
```json
{
  "type": "claims-fnol",
  "description": "On March 15 2026 at 2pm, insured vehicle rear-ended a truck at the intersection of 5th Ave and Main St, resulting in $8,000 estimated damage to front bumper and hood. No injuries reported. Police report #2026-4821 filed.",
  "file": "police_report.pdf"
}
```

### Expected Output

The pod returns a **markdown-rendered analysis report** (`FNOL Analysis Report`) containing:

| Section | Description |
|---------|-------------|
| **Incident Summary** | Structured recap of the loss event |
| **Loss Classification** | Line of business, peril type, coverage trigger |
| **Parties Involved** | Insured, third parties, witnesses |
| **Initial Coverage Assessment** | Whether the described loss appears covered under standard policy lines |
| **Documentation Checklist** | Required supporting documents still needed |
| **Recommended Next Steps** | Immediate actions for the broker/adjuster |
| **Subrogation Flag** | Whether recovery from a third party may be possible |
| **Fraud Indicators** | Any patterns that warrant additional review |

**Structured fields stored in `extracted_json` (in `pod_extraction_runs`):**
```json
{
  "incident_date": "2026-03-15",
  "incident_location": "5th Ave & Main St",
  "loss_type": "collision",
  "line_of_business": "auto",
  "estimated_damage": 8000,
  "injuries_reported": false,
  "police_report_number": "2026-4821",
  "parties": [
    { "role": "insured", "name": "..." },
    { "role": "third_party", "name": "..." }
  ],
  "coverage_applicable": true,
  "subrogation_potential": true,
  "documentation_required": ["repair_estimate", "police_report", "photos"],
  "recommended_actions": ["..."],
  "confidence_notes": "..."
}
```

**Confidence**: Score 0.0–1.0 reflecting clarity of incident description and document quality.  
**Auto-approve threshold**: `POD_CONFIDENCE_THRESHOLD` (default `0.85`).

---

## Pod 2 — Quote Generation

### Identity

| Field | Value |
|-------|-------|
| **Pod ID** | `quote-generation` |
| **Category** | Automation |
| **Segment** | Broker |
| **Pack** | Underwriting Pack |
| **Frontend UI** | `frontend/src/components/playground/QuoteGenerationUI.tsx` |
| **API prefix** | `/api/pods/quote-generation` |

### Description

The Quote Generation pod navigates carrier websites or carrier APIs, submits coverage applications on behalf of the insured, collects quotes, and produces a side-by-side comparison proposal. It supports 18 major US carriers across 6 lines of business and outputs a downloadable PDF proposal and email-ready summary.

### Required Input

The UI collects input in structured steps (input → fetching → compare → proposal).

**Step 1 — Coverage Setup**

| Field | Type | Required | Options |
|-------|------|----------|---------|
| `insuranceType` | `string` (select) | **Yes** | `auto`, `home`, `commercial`, `general-liability`, `workers-comp`, `professional-liability` |
| `selectedCarriers` | `string[]` (multi-select) | **Yes** (≥1) | See carrier list below |

**Supported Carriers (18):**

| ID | Display Name |
|----|-------------|
| `progressive` | Progressive |
| `geico` | GEICO |
| `state-farm` | State Farm |
| `allstate` | Allstate |
| `liberty-mutual` | Liberty Mutual |
| `travelers` | Travelers |
| `nationwide` | Nationwide |
| `farmers` | Farmers Insurance |
| `usaa` | USAA |
| `american-family` | American Family |
| `hartford` | The Hartford |
| `chubb` | Chubb |
| `aig` | AIG |
| `zurich` | Zurich |
| `hanover` | The Hanover |
| `cincinnati` | Cincinnati Insurance |
| `erie` | Erie Insurance |
| `auto-owners` | Auto-Owners |

**Step 2 — Applicant Information**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | `string` | **Yes** | Individual insured full name |
| `businessName` | `string` | No | Required for commercial lines |
| `email` | `string` | **Yes** | Proposal delivery address |
| `phone` | `string` | No | Contact number |
| `address` | `string` | **Yes** | Risk location |
| `coverageAmount` | `number` | **Yes** | Desired coverage limit (USD) |

### Expected Output

The pod produces a multi-section structured response:

**`CarrierQuote` object (one per selected carrier):**
```typescript
{
  carrier: string              // e.g. "Progressive"
  logo: string                 // Carrier logo URL
  premium: number              // Annual premium in USD
  coverage: string             // Coverage description
  deductible: number           // Deductible in USD
  status: "pending" | "fetching" | "complete" | "error"
  features: string[]           // Coverage highlights
  rating?: number              // Customer satisfaction rating (1-5)
  claimsScore?: number         // Claims satisfaction score
  financialStrength?: string   // AM Best / S&P rating
}
```

**UI output tabs / sections:**

| Section | Description |
|---------|-------------|
| **Quote Comparison Table** | Side-by-side premium, deductible, coverage, features for all carriers |
| **Premium Analysis** | Lowest / highest / average premium, savings potential |
| **Coverage Details** | Per-carrier policy terms, limits, exclusions |
| **AI Recommendation** | Ranked carrier recommendation with rationale |
| **Proposal PDF** | Downloadable client-ready PDF proposal |
| **Email Preview** | Draft email with proposal attachment ready to send |

**Structured fields stored in `extracted_json`:**
```json
{
  "insurance_type": "auto",
  "applicant": {
    "name": "...",
    "business_name": "...",
    "email": "...",
    "phone": "...",
    "address": "...",
    "coverage_amount": 500000
  },
  "quotes": [
    {
      "carrier": "Progressive",
      "premium": 1240,
      "coverage": "Full Coverage",
      "deductible": 500,
      "features": ["Accident Forgiveness", "Snapshot Discount"],
      "status": "complete",
      "rating": 4.2,
      "financial_strength": "A+"
    }
  ],
  "recommended_carrier": "Progressive",
  "recommendation_rationale": "Lowest premium with comparable coverage and strong claims score.",
  "total_savings_potential": 380
}
```

---

## Pod 3 — Policy Comparison

### Identity

| Field | Value |
|-------|-------|
| **Pod ID** | `policy-comparison` |
| **Category** | Analysis |
| **Segment** | Broker |
| **Pack** | Underwriting Pack, Distribution Pack |
| **Frontend UI** | `frontend/src/components/playground/PolicyComparisonUI.tsx` |
| **Prompt builder** | `frontend/src/lib/policyComparisonPrompt.ts` |
| **API prefix** | `/api/pods/policy-comparison` |

### Description

The Policy Comparison pod accepts two insurance policy documents (current/expiring vs. proposed/renewal) and performs a deep structural analysis. It extracts key coverage fields from both documents, computes a clause-level diff (redline), calculates a deviation percentage, and produces a materiality-weighted recommendation for which policy to choose. If premiums exceed a configurable threshold, it can trigger a Quote Generation recommendation.

### Required Input

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `policyAFile` | `File` (PDF / DOCX) | **Yes** | Current / expiring policy |
| `policyBFile` | `File` (PDF / DOCX) | **Yes** | Proposed / renewal policy |
| `policyAName` | `string` | Auto | Derived from filename |
| `policyBName` | `string` | Auto | Derived from filename |
| `deviationThresholdPercent` | `number` | No | Default `10`. Triggers recommendation when exceeded. |

**Document constraints**: Each document is capped at 40,000 characters before being sent to the model (truncated with `[TRUNCATED]` marker if exceeded).

### System Prompt (LLM Instructions)

The pod uses a strict JSON-only prompt (no prose outside JSON allowed):

```
You are a policy checking engine for insurance documents.
Compare two policy documents and produce a STRICT JSON object only.

Rules:
- Compute deviation_percent as 0..100 (% of materially changed coverage/clauses)
- Set deviation_exceeds_threshold = deviation_percent > {threshold}
- If deviation_exceeds_threshold, include recommendation with recommended_policy (A|B|NEITHER) and rationale list
- Always include clause_diff.clauses[] with status=added|removed|changed
- Always include extracted_fields.policyA and extracted_fields.policyB with: 
  carrier, premiums, limits, deductibles, effective dates, exclusions, endorsements
- Include taxonomy fields (domain, doc types, LOB)
- If data is missing, keep keys but set values to null + add a warning
```

### Expected Output

**`PolicyComparisonStructured` schema:**

```typescript
{
  taxonomy: {
    domain: "insurance",
    doc_type_a: string,           // e.g. "Commercial General Liability Policy"
    doc_type_b: string,           // e.g. "Commercial General Liability Renewal"
    lines_of_business: string[]   // e.g. ["GL", "PROPERTY"]
  },

  extracted_fields: {
    policyA: {
      carrier?: string,
      premium?: number,
      general_liability?: string,
      deductible?: number,
      cyber_coverage?: boolean,
      epl_coverage?: boolean,
      water_damage?: boolean,
      effective_date?: string,
      expiration_date?: string,
      exclusions?: string[],
      endorsements?: string[],
      // ... any additional extractable fields
    },
    policyB: { /* same structure */ }
  },

  clause_diff: {
    clauses: [
      {
        id: string,              // Unique clause identifier
        title?: string,          // Clause heading
        status: "added" | "removed" | "changed",
        before?: string,         // Policy A text (for changed/removed)
        after?: string,          // Policy B text (for changed/added)
        path?: string            // Document section path
      }
    ],
    meta?: object                // Additional diff metadata
  },

  deviation_percent: number,               // 0–100
  deviation_exceeds_threshold: boolean,    // true if > deviationThresholdPercent

  recommendation?: {
    recommended_policy: "A" | "B" | "NEITHER",
    rationale: string[]          // Bullet-point reasoning
  },

  warnings: string[]             // Missing data, ambiguous fields, etc.
}
```

**UI output views:**

| View | Description |
|------|-------------|
| **Coverage View** (default) | Side-by-side field comparison table with premium diff, coverage gap highlights |
| **Clause Redline View** | Clause-level diff showing additions (green), removals (red), changes (yellow) |
| **AI Recommendation Banner** | Policy A vs B vs Review recommendation with rationale |
| **Smart Quote Recommendation** | Shown when either premium exceeds `policyComparisonPremiumThreshold` and smart recommendations are enabled |

**Confidence scoring**: Applied to the quality of field extraction; low-confidence runs are queued for admin review.

---

## Pod 4 — ACORD Form Extraction

### Identity

| Field | Value |
|-------|-------|
| **Pod ID** | `acord_form_understanding` |
| **Category** | Document Processing |
| **Segment** | Broker |
| **Pack** | Underwriting Pack |
| **Frontend UI** | `frontend/src/components/playground/ACORDParserUI.tsx` |
| **Backend schemas** | `backend/Models/acord_form_understanding/schemas.py` |
| **API prefix** | `/api/acord` (dedicated router — not generic `/api/pods`) |

### Description

The ACORD Form Extraction pod parses and extracts structured data from ACORD standard insurance forms. It supports 8 form types (ACORD 25, 27, 80, 85, 90, 125, 126, 140) using a multi-engine pipeline: fillable AcroForm widget extraction, multi-engine PDF-to-text, OCR (Tesseract / PaddleOCR), and LLM-based structured field extraction (RunPod fine-tuned model with OpenAI fallback). The extracted data is normalized into a comprehensive schema covering producer, insured, coverages, premises, loss history, and more.

### Supported Form Types

| Form | Name | Use Case |
|------|------|----------|
| ACORD 25 | Certificate of Insurance | Proof of coverage for third parties |
| ACORD 27 | Evidence of Property Insurance | Mortgage / lender property proof |
| ACORD 80 | Garage Coverage Summary | Auto dealer / garage operations |
| ACORD 85 | General Liability Application | GL coverage application |
| ACORD 90 | Automobile Application | Commercial auto application |
| ACORD 125 | Commercial Insurance Application | Full commercial lines application |
| ACORD 126 | Commercial General Liability | CGL supplement / schedule |
| ACORD 140 | Property Loss Notice | Property claim first notice |

### Required Input

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `formType` | `string` (select) | **Yes** | One of: `ACORD 25`, `ACORD 27`, `ACORD 80`, `ACORD 85`, `ACORD 90`, `ACORD 125`, `ACORD 126`, `ACORD 140` |
| `file` | `File` (PDF / DOCX) | **Yes** | The ACORD form document. Supports fillable PDFs and scanned/flattened images. |
| `extraction_hint` | `string` | No | Optional hint to guide re-extraction (used with `POST /re-extract`) |

### Extraction Pipeline

1. **PDF classification** — detect fillable (AcroForm) vs flattened (scanned/print)
2. **Text extraction** — try engines in order: BytesScout → pdfplumber → PyMuPDF → PyPDF2
3. **AcroForm extraction** — extract fillable widget values if PDF has AcroForm layer
4. **OCR** — Tesseract or PaddleOCR for raster/scanned documents
5. **LLM structured extraction** — RunPod fine-tuned model (fallback: OpenAI)
6. **Form-type-specific fallbacks** — `acord25_fallback.py`, `acord125_fallback.py`
7. **Azure Document Intelligence** — optional high-accuracy OCR overlay
8. **Confidence scoring** — base score from engine + overlay adjustments
9. **Post-processing** — normalization, validation, null handling

### Expected Output — `AcordFormSummary` Schema

Full schema defined in `backend/Models/acord_form_understanding/schemas.py`.

```python
AcordFormSummary {

  # Form identification
  form_type: str                    # e.g. "ACORD 25", "ACORD 125"
  form_version: str
  certificate_number: str
  revision_date: str
  date: str                         # MM/DD/YYYY

  # Producer (agency)
  producer: AcordProducer {
    name: str
    contact_name: str
    address, city, state, postal_code: str
    phone, fax, email: str
    agency_customer_id: str
    subcode: str
    producer_license_no: str
    national_producer_number: str
  }

  # Primary insured
  insured: AcordInsured {
    name: str                       # Named insured (with name_confidence score)
    name_confidence: float          # 0.0–1.0
    contact_name: str
    mailing_address, city, state, postal_code: str
    phone, fax, email, website: str
    entity_type: str                # Corporation / LLC / Partnership / Individual / Trust
    gl_code, sic, naics: str
    fein: str                       # Federal Employer Identification Number
  }

  # Additional named insureds (ACORD 125 page 1)
  other_named_insureds: List[AcordOtherNamedInsured] {
    name, mailing_address, city, state, postal_code: str
    phone, website, entity_type: str
    gl_code, sic, naics, fein: str
  }

  # Certificate holder / additional insured
  holder: AcordHolder {
    name, address, city, state, postal_code: str
    is_additional_insured: bool
    is_subrogation_waived: bool
  }

  # Policy-level information
  policy_info: AcordPolicyInfo {
    carrier: AcordCarrier { name: str, naic_number: str }
    program_name, program_code: str
    policy_number: str
    proposed_eff_date, proposed_exp_date: str
    billing_plan: str               # Direct / Agency
    payment_plan: str               # Annual / Monthly / etc.
    method_of_payment: str          # Cash / EFT / etc.
    deposit, minimum_premium, policy_premium: str
    transaction_type: str           # Quote / Issue / Renew / Change / Cancel
    transaction_date: str
    underwriter, underwriter_office: str
  }

  # Lines of business indicated on form
  lines_of_business_indicated: List[str]
  # e.g. ["BUSINESS OWNERS", "COMMERCIAL GENERAL LIABILITY", "WORKERS COMPENSATION"]

  # Coverage details (one entry per line of business)
  coverages: List[AcordPolicyCoverage] {
    line_of_business: str           # GL | AUTO | WC | UMB | PROPERTY | CRIME | etc.
    policy_number: str
    effective_date, expiration_date: str
    claims_made: bool
    occurrence_type: bool
    additional_insured: bool
    waiver_of_subrogation: bool

    # General Liability limits
    each_occurrence: str
    damage_to_rented_premises: str
    medical_expense: str
    personal_advertising_injury: str
    general_aggregate: str
    products_comp_ops_aggregate: str

    # Automobile limits
    combined_single_limit: str
    bodily_injury_per_person: str
    bodily_injury_per_accident: str
    property_damage: str

    # Umbrella / Excess
    occurrence_limit: str
    aggregate_limit: str
    deductible: str
    retention: str
    retroactive_date: str

    # Workers Compensation
    wc_statutory_limits: bool
    employer_liability_each_accident: str
    employer_liability_each_employee: str
    employer_liability_policy_limit: str

    insurers: List[AcordCarrier]
  }

  # Business premises / locations
  premises: List[AcordPremises] {
    location_number, street, city, state, county, zip: str
    interest: str                   # Owner Occupied / Tenant / etc.
    full_time_employees: str
    part_time_employees: str
    annual_revenues: str
    total_building_area_sqft: str
    description_of_operations: str
    area_leased_to_others: str
  }

  # Prior insurance carriers
  prior_carriers: List[AcordPriorCarrier] {
    year, category: str
    carrier, policy_number: str
    premium, effective_date, expiration_date: str
  }

  # Loss history (5 years typically)
  loss_history: List[AcordLossHistory] {
    date_of_occurrence: str
    line_type: str
    description: str
    date_of_claim: str
    amount_paid: str
    amount_reserved: str
    subrogation: bool
    claim_open: bool
  }

  # Additional interests (loss payees, mortgagees, etc.)
  additional_interests: List[AcordAdditionalInterest] {
    interest_type: str              # Additional Insured / Loss Payee / Mortgagee / etc.
    name, address: str
    location, building: str
    loan_reference: str
  }

  # Free-text sections
  description_of_operations: str
  nature_of_business: str
  cancellation_notice_days: int
  additional_remarks: str

  # Overflow fields not in standard schema
  extra_fields: dict

  # Extraction diagnostics
  extraction_meta: ExtractionMeta {
    form_type_detected: str
    blank_in_document: List[str]          # Fields present but empty
    not_applicable_to_form_type: List[str] # Fields not on this form type
    all_checked_items: List[str]           # Every checked checkbox
    remarks: List[str]                     # Ambiguity notes from LLM
    extraction_engine: str                 # bytescout|pdfplumber|pymupdf|pypdf2|ocr|txt|legacy
    base_confidence: float                 # Engine-derived base score
    structured_response_source: str        # LLM RunPod | LLM OpenAI | Fallback
    pdf_form_classification: str           # fillable | flattened
    ocr_text_engine: str                   # tesseract | paddle
  }

  overall_confidence: float               # 0.0–1.0
  raw_text: str                           # Original extracted text
}
```

### ACORD-Specific API Endpoints

The ACORD pod has its own dedicated router at `/api/acord` (in addition to the generic `/api/pods/acord_form_understanding` endpoints).

**User Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/acord/extract` | Synchronous extraction. Returns full `AcordFormSummary`. |
| `POST` | `/api/acord/extract/start` | Start asynchronous extraction job. Returns `job_id`. |
| `GET` | `/api/acord/extract/status/{job_id}` | Poll async job status and result. |
| `GET` | `/api/acord/runs` | List user's past extractions (paginated). |
| `GET` | `/api/acord/runs/{run_id}` | Get extraction details + metadata. |
| `POST` | `/api/acord/runs/{run_id}/submit` | Submit run for admin review / training queue. |
| `POST` | `/api/acord/runs/{run_id}/re-extract` | Re-extract with optional hint string. |

**Admin Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/acord/admin/queue` | View admin review queue |
| `POST` | `/api/acord/admin/{run_id}/review` | Single run admin review decision |
| `POST` | `/api/acord/admin/batch-review` | Batch review multiple runs |
| `GET` | `/api/acord/admin/queue/stats` | Queue statistics |
| `GET` | `/api/acord/admin/queue/{run_id}/detail` | Full queue item detail |
| `PATCH` | `/api/acord/admin/queue/{run_id}/detail` | Update queue item |
| `GET` | `/api/acord/admin/jobs` | List training jobs |
| `GET` | `/api/acord/admin/jobs/{job_id}` | Training job details |
| `GET` | `/api/acord/admin/jobs/{job_id}/eval` | Evaluation results |
| `GET` | `/api/acord/admin/jobs/{job_id}/log` | Training logs |
| `GET` | `/api/acord/admin/runs/{run_id}/health-card` | Confidence + feedback health |

### ACORD-Specific Database Tables

In addition to the shared pod tables, ACORD has its own dedicated tables (defined in `supabase/migrations/20260318120000_acord_extraction_workflow.sql` and related migrations):

| Table | Purpose |
|-------|---------|
| `acord_extraction_runs` | ACORD-specific run records (mirrors `pod_extraction_runs` with ACORD fields) |
| `acord_extraction_feedback` | User/admin corrections for ACORD runs |
| `acord_admin_queue` | Admin review queue for ACORD runs |
| `acord_training_jobs` | Fine-tuning jobs for the ACORD model |
| `acord_eval_results` | Evaluation metrics per ACORD training job |

### Frontend Output Tabs (ACORDParserUI)

| Tab | Description |
|-----|-------------|
| **JSON View** | Full normalized `AcordFormSummary` as formatted JSON |
| **Fields View** | Flattened key-value table for quick review |
| **Edit Mode** | Inline JSON editor for user corrections |
| **Changes View** | Diff view before/after user edits |
| **Split View** | Side-by-side original document vs. extracted fields |

### Fine-Tuning Pipeline

Located in `backend/fine_tuning/acord_form_pipeline/`:

| File | Purpose |
|------|---------|
| `schema.py` | 6-field hardened extraction schema for fine-tuning |
| `schema_registry.py` | Schema versioning and management |
| `build_dataset.py` | Single-form dataset construction |
| `build_multiform_dataset.py` | Multi-form type dataset |
| `clean_ocr.py` | OCR noise cleaning |
| `ocr_extract.py` | OCR text extraction |
| `postprocess.py` | Normalization and validation |
| `train_qlora_chat.py` | QLoRA fine-tuning (single form) |
| `train_multiform_qlora.py` | QLoRA fine-tuning (multi-form) |
| `evaluate_extraction.py` | Single-form evaluation |
| `evaluate_multiform.py` | Multi-form evaluation |
| `inference_production.py` | Production inference runner |

**Quality Gate thresholds** (env vars, all configurable):

| Variable | Default | Meaning |
|----------|---------|---------|
| `FT_ACORD_QG_MIN_JSON_VALID_RATE` | `0.90` | ≥90% of outputs must be valid JSON |
| `FT_ACORD_QG_MIN_JSON_EXACT_MATCH` | `0.70` | ≥70% exact field match rate |
| `FT_ACORD_QG_MIN_JSON_FIELD_RECALL` | `0.80` | ≥80% field recall |
| `FT_ACORD_QG_MAX_JSON_EXTRA_FIELD_RATE` | `0.10` | ≤10% extra/hallucinated fields |
| `FT_ACORD_QG_MAX_OOS_HALLUCINATION_RATE` | `0.25` | ≤25% hallucination on out-of-sample set |

---

## Confidence & Training Workflow

### Confidence Score Adjustments

Starting from the base model confidence, the following adjustments are applied (defined in `backend/app/services/pod_extraction.py`):

| Signal | Adjustment |
|--------|-----------|
| Latest feedback is thumbs_up | `+0.05` |
| Latest feedback is thumbs_down | `−0.08` |
| JSON was manually corrected by user | `−0.10` |
| Admin approved the run | `+0.04` |
| Admin rejected or requested rework | `−0.06` |

Final score is clamped to `[0.0, 1.0]`.

### Auto-Approve Logic

```
if thumbs_up == true AND adjusted_confidence >= POD_CONFIDENCE_THRESHOLD:
    status = "approved"
    trigger_training_job() if AUTO_FINE_TUNE_ON_POD_APPROVAL
else:
    status = "needs_admin_review"
    create pod_admin_queue entry
```

### Evaluation Sets

After each training job, four evaluation sets are scored:

| Set | Description |
|-----|-------------|
| `seen` | Training examples (sanity check) |
| `paraphrased` | Rephrased versions of training examples |
| `oos` | Out-of-sample documents not in training set |
| `combined` | Weighted combination of all sets |

---

## Environment Variables

| Variable | Default | Applies To | Description |
|----------|---------|-----------|-------------|
| `POD_CONFIDENCE_THRESHOLD` | `0.85` | All pods | Minimum confidence for auto-approval |
| `ACORD_CONFIDENCE_THRESHOLD` | `0.85` | ACORD only | ACORD-specific threshold override |
| `AUTO_FINE_TUNE_ON_POD_APPROVAL` | `true` | All pods | Trigger training job on admin approval |
| `ACORD_POD_ID` | `acord_form_understanding` | ACORD | Pod identifier string |
| `RUNPOD_POD_ID` | — | ACORD | RunPod ML service instance ID |
| `FT_ACORD_QG_MIN_JSON_VALID_RATE` | `0.90` | ACORD training | Quality gate: valid JSON rate |
| `FT_ACORD_QG_MIN_JSON_EXACT_MATCH` | `0.70` | ACORD training | Quality gate: exact match rate |
| `FT_ACORD_QG_MIN_JSON_FIELD_RECALL` | `0.80` | ACORD training | Quality gate: field recall |
| `FT_ACORD_QG_MAX_JSON_EXTRA_FIELD_RATE` | `0.10` | ACORD training | Quality gate: max extra field rate |
| `FT_ACORD_QG_MAX_OOS_HALLUCINATION_RATE` | `0.25` | ACORD training | Quality gate: max hallucination rate |

---

*End of document.*
