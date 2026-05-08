from __future__ import annotations

from typing import Any, Dict

FIXED_SCHEMA_KEYS = [
    "agency_name",
    "contact_name",
    "carrier",
    "policy_number",
    "email",
    "phone",
]

# Production contract: values are string or null at runtime.
SCHEMA: Dict[str, type] = {
    "agency_name": str,
    "contact_name": str,
    "carrier": str,
    "policy_number": str,
    "email": str,
    "phone": str,
}

SYSTEM_PROMPT = (
    "You are a strict ACORD-oriented information extraction system.\n\n"
    "Rules:\n"
    "- Output ONLY valid JSON\n"
    "- Do NOT add explanations, markdown fences, or commentary\n"
    "- Do NOT include extraction metadata, pipeline provenance, or confidence scores\n"
    "- Do NOT infer missing data\n"
    "- If a value is not explicitly present in the input, return null\n"
    "- Do NOT hallucinate\n"
    "- Ensure all fields are present in output\n"
    "- CRITICAL: All values MUST be copied EXACTLY from the input text\n"
    "- Do NOT rephrase, normalize, or infer values\n"
    "- If exact value is not found in input text, return null\n\n"
    "Output JSON schema (all keys required):\n"
    "{\n"
    '  "agency_name": string | null,\n'
    '  "contact_name": string | null,\n'
    '  "carrier": string | null,\n'
    '  "policy_number": string | null,\n'
    '  "email": string | null,\n'
    '  "phone": string | null\n'
    "}\n\n"
    "Example output:\n"
    "{\n"
    '  "agency_name": "ABC Insurance",\n'
    '  "contact_name": null,\n'
    '  "carrier": "XYZ Carrier",\n'
    '  "policy_number": "PN-12345",\n'
    '  "email": null,\n'
    '  "phone": "(630) 555-0244"\n'
    "}"
)

USER_PROMPT_TEMPLATE = (
    "Extract structured data from the following document.\n\n"
    "Return ONLY valid JSON.\n\n"
    "Document:\n"
    "{input_text}"
)


def normalize_label(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure all schema keys exist, unknown keys are ignored, missing -> null.
    """
    out: Dict[str, Any] = {}
    for key in FIXED_SCHEMA_KEYS:
        val = record.get(key)
        if val is None:
            out[key] = None
            continue
        txt = str(val).strip()
        out[key] = txt if txt else None
    return out

