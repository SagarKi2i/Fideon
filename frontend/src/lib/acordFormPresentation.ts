/**
 * ACORD form–specific labels and field-section layout for the extraction UI.
 * Keep in sync with backend AcordFormSummary / form_type_detected.
 */

export type FieldDef = { path: string; label: string; type?: "text" | "textarea" | "bool" };

export type SectionDef = { id: string; title: string; fields: FieldDef[] };

/** Normalize "ACORD 25", "25", " acord 125 " → "25" | "125" | … */
export function normalizeAcordFormKey(raw: string | null | undefined): string {
  if (!raw || typeof raw !== "string") return "25";
  const m = raw.trim().toUpperCase().match(/\b(\d{2,3})\b/);
  return m ? m[1] : "25";
}

export type FormPresentation = {
  /** Badge title, e.g. "ACORD 125" */
  title: string;
  /** One-line description under the badge */
  subtitle: string;
};

const PRESENTATION: Record<string, FormPresentation> = {
  "25": {
    title: "ACORD 25",
    subtitle: "Certificate of liability insurance",
  },
  "27": {
    title: "ACORD 27",
    subtitle: "Evidence of property insurance",
  },
  "80": {
    title: "ACORD 80",
    subtitle: "Garage coverage summary",
  },
  "85": {
    title: "ACORD 85",
    subtitle: "General liability application",
  },
  "90": {
    title: "ACORD 90",
    subtitle: "Automobile liability application",
  },
  "125": {
    title: "ACORD 125",
    subtitle: "Commercial insurance application",
  },
  "126": {
    title: "ACORD 126",
    subtitle: "Commercial general liability section",
  },
  "140": {
    title: "ACORD 140",
    subtitle: "Property loss notice",
  },
};

export function getFormPresentation(formType: string | null | undefined): FormPresentation {
  const key = normalizeAcordFormKey(formType);
  return (
    PRESENTATION[key] ?? {
      title: `ACORD ${key}`,
      subtitle: "Insurance form extraction",
    }
  );
}

// ── Field sections (ids referenced by layout per form) ────────────────────────

const SECTION_PRODUCER: SectionDef = {
  id: "producer",
  title: "Producer / agency",
  fields: [
    { path: "producer.name", label: "Agency name" },
    { path: "producer.contact_name", label: "Contact name" },
    { path: "producer.address", label: "Address" },
    { path: "producer.city", label: "City" },
    { path: "producer.state", label: "State" },
    { path: "producer.postal_code", label: "Postal code" },
    { path: "producer.phone", label: "Phone" },
    { path: "producer.fax", label: "Fax" },
    { path: "producer.email", label: "Email" },
    { path: "producer.agency_customer_id", label: "Agency customer ID" },
    { path: "producer.subcode", label: "Subcode" },
    { path: "producer.producer_license_no", label: "Producer license #" },
    { path: "producer.national_producer_number", label: "National producer #" },
  ],
};

const SECTION_INSURED: SectionDef = {
  id: "insured",
  title: "Named insured",
  fields: [
    { path: "insured.name", label: "Name" },
    { path: "insured.mailing_address", label: "Mailing address" },
    { path: "insured.city", label: "City" },
    { path: "insured.state", label: "State" },
    { path: "insured.postal_code", label: "Postal code" },
    { path: "insured.phone", label: "Phone" },
    { path: "insured.fax", label: "Fax" },
    { path: "insured.email", label: "Email" },
    { path: "insured.website", label: "Website" },
    { path: "insured.entity_type", label: "Entity type" },
    { path: "insured.gl_code", label: "GL code" },
    { path: "insured.sic", label: "SIC" },
    { path: "insured.naics", label: "NAICS" },
    { path: "insured.fein", label: "FEIN" },
  ],
};

const SECTION_POLICY: SectionDef = {
  id: "policy_info",
  title: "Policy information",
  fields: [
    { path: "policy_info.carrier.name", label: "Carrier name" },
    { path: "policy_info.carrier.naic_number", label: "Carrier NAIC #" },
    { path: "policy_info.program_name", label: "Program name" },
    { path: "policy_info.program_code", label: "Program code" },
    { path: "policy_info.policy_number", label: "Policy number" },
    { path: "policy_info.proposed_eff_date", label: "Proposed effective" },
    { path: "policy_info.proposed_exp_date", label: "Proposed expiration" },
    { path: "policy_info.billing_plan", label: "Billing plan" },
    { path: "policy_info.payment_plan", label: "Payment plan" },
    { path: "policy_info.method_of_payment", label: "Payment method" },
    { path: "policy_info.deposit", label: "Deposit" },
    { path: "policy_info.minimum_premium", label: "Minimum premium" },
    { path: "policy_info.policy_premium", label: "Policy premium" },
    { path: "policy_info.transaction_type", label: "Transaction type" },
    { path: "policy_info.underwriter", label: "Underwriter" },
    { path: "policy_info.underwriter_office", label: "Underwriter office" },
  ],
};

const SECTION_HOLDER: SectionDef = {
  id: "holder",
  title: "Certificate holder",
  fields: [
    { path: "holder.name", label: "Name" },
    { path: "holder.address", label: "Address" },
    { path: "holder.city", label: "City" },
    { path: "holder.state", label: "State" },
    { path: "holder.postal_code", label: "Postal code" },
  ],
};

const SECTION_CERT_META: SectionDef = {
  id: "certificate_meta",
  title: "Certificate",
  fields: [
    { path: "certificate_number", label: "Certificate #" },
    { path: "date", label: "Certificate date" },
    { path: "revision_date", label: "Revision" },
    { path: "cancellation_notice_days", label: "Cancellation notice (days)" },
  ],
};

const SECTION_APP_META: SectionDef = {
  id: "application_meta",
  title: "Application details",
  fields: [
    { path: "description_of_operations", label: "Description of operations", type: "textarea" },
    { path: "nature_of_business", label: "Nature of business" },
    { path: "additional_remarks", label: "Additional remarks", type: "textarea" },
  ],
};

const SECTION_REGISTRY: Record<string, SectionDef> = {
  producer: SECTION_PRODUCER,
  insured: SECTION_INSURED,
  policy_info: SECTION_POLICY,
  holder: SECTION_HOLDER,
  certificate_meta: SECTION_CERT_META,
  application_meta: SECTION_APP_META,
};

/**
 * Which section ids to show, in order, for each form number.
 * Certificate-style (25, 27, …): holder + certificate_meta matter.
 * Application-style (125, 85, 90): policy_info + application_meta; no certificate holder.
 */
const LAYOUT: Record<string, string[]> = {
  // Certificate of insurance — emphasize holder & coverages (coverages rendered separately in UI)
  "25": ["producer", "insured", "holder", "certificate_meta", "policy_info"],
  "27": ["producer", "insured", "holder", "certificate_meta", "policy_info"],
  "126": ["producer", "insured", "holder", "certificate_meta", "policy_info"],

  // Full applications
  "125": ["producer", "insured", "policy_info", "application_meta"],
  "85": ["producer", "insured", "policy_info", "application_meta"],
  "90": ["producer", "insured", "policy_info", "application_meta"],

  // Garage / property notice / CGL section — balanced
  "80": ["producer", "insured", "policy_info", "holder", "certificate_meta"],
  "140": ["producer", "insured", "policy_info", "application_meta"],

  default: ["producer", "insured", "policy_info", "holder", "certificate_meta", "application_meta"],
};

export function getFieldSectionsForFormType(formType: string | null | undefined): SectionDef[] {
  const key = normalizeAcordFormKey(formType);
  const ids = LAYOUT[key] ?? LAYOUT.default;
  return ids.map((id: any) => SECTION_REGISTRY[id]).filter(Boolean);
}
