"""
Hardcoded out-of-scope (non–ACORD-125) training/eval examples for refusal / error JSON.
Output schema is fixed — do not use the six-field extraction object here.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List

# Single canonical JSON line the model should emit for OOS content.
OOS_OUTPUT_JSON = '{"error": "not_acord_125", "extracted": null}'

OOS_SYSTEM_RULES = (
    "You classify and extract insurance form data. "
    "If the document is NOT a valid ACORD 125 application with extractable producer/policy fields, "
    "respond with exactly this JSON and nothing else: "
    + OOS_OUTPUT_JSON
)

# Categories (>=2 examples each in the combined pool where possible).
# Train uses first 15 rows; holdout uses last 5 rows (see OOS_TRAIN_EXAMPLES / OOS_HOLDOUT_EXAMPLES).

_OOS_POOL: List[Dict[str, Any]] = [
    # Plain English / email (not a form) — 2+
    {
        "input": "Hi Sarah,\n\nCan you send the updated loss runs by Friday? Thanks,\nMike",
        "category": "plain_text",
    },
    {
        "input": "Subject: Lunch\n\nAre we still meeting at noon at the cafe downtown?",
        "category": "plain_text",
    },
    # Wrong ACORD form type — 2+
    {
        "input": "ACORD 126 — COMMERCIAL GENERAL LIABILITY SECTION\n"
        "DECLARATIONS\nNamed Insured: ABC LLC\nPolicy Number: GL-998877",
        "category": "wrong_form_type",
    },
    {
        "input": "ACORD 140 — CERTIFICATE OF PROPERTY INSURANCE\n"
        "LOCATION / PREMISES: 100 Main St, Chicago IL\nCarrier: XYZ Insurance Co.",
        "category": "wrong_form_type",
    },
    # Blank / whitespace — 2+
    {"input": "", "category": "blank"},
    {"input": "   \n\n\t  ", "category": "blank"},
    # Random JSON — 2+
    {
        "input": '{"foo": 1, "bar": [2, 3], "nested": {"x": true}}',
        "category": "random_json",
    },
    {
        "input": "[null, false, {\"k\": \"v\"}]",
        "category": "random_json",
    },
    # Certificate of insurance / not application — 2+
    {
        "input": "CERTIFICATE OF LIABILITY INSURANCE\n"
        "THIS CERTIFICATE IS ISSUED AS A MATTER OF INFORMATION ONLY.\n"
        "INSURED: Contractor LLC\nCERTIFICATE HOLDER: City of Springfield",
        "category": "certificate",
    },
    {
        "input": "EVIDENCE OF PROPERTY INSURANCE\n"
        "Loan Number: 5544332211\nMortgagee: First National Bank",
        "category": "certificate",
    },
    # Medical / non-insurance — 2+
    {
        "input": "Patient: Jane Doe DOB 01/15/1980\nChief complaint: persistent cough. Plan: chest X-ray.",
        "category": "medical",
    },
    {
        "input": "OPERATIVE REPORT\nProcedure: appendectomy\nSurgeon: Dr. Smith\nFindings: acute appendicitis.",
        "category": "medical",
    },
    # Garbled OCR — 2+
    {
        "input": "|||@@@### qwwxz ~~~ lorem ipsum dolor sit amet @@@###|||",
        "category": "garbled_ocr",
    },
    {
        "input": "FfFfFf 1234 @@@@ ---- .... .... INSURANCE .... @@@@",
        "category": "garbled_ocr",
    },
    # Extra rows to reach 20 total (mixed categories)
    {
        "input": "Meeting notes: Q3 roadmap, hiring plan, no insurance content here.",
        "category": "plain_text",
    },
    {
        "input": "ACORD 140 SUPPLEMENT\nVEHICLE SCHEDULE\nYear 2019 Ford F-150 VIN 1FTFW1ET5DFC12345",
        "category": "wrong_form_type",
    },
    {
        "input": "NOTICE TO HOLDER: This is not an application. Coverage may not apply.",
        "category": "certificate",
    },
    {
        "input": "Lab results: WBC 7.2, glucose 99 mg/dL. No policy numbers.",
        "category": "medical",
    },
    {
        "input": "{\"not\": \"a form\", \"just\": \"json pasted in email\"}",
        "category": "random_json",
    },
    {
        "input": "TThhiiss  iiss  ddoouubbllee  vviissiioonn  OCR  tteesstt",
        "category": "garbled_ocr",
    },
]

# Exactly 15 train + 5 holdout = 20
OOS_TRAIN_EXAMPLES: List[Dict[str, Any]] = []
OOS_HOLDOUT_EXAMPLES: List[Dict[str, Any]] = []

for i, row in enumerate(_OOS_POOL[:20]):
    rec = {
        "input": row["input"],
        "output": OOS_OUTPUT_JSON,
        "category": row["category"],
    }
    if i < 15:
        OOS_TRAIN_EXAMPLES.append(rec)
    else:
        OOS_HOLDOUT_EXAMPLES.append(rec)


def to_sft_record(ex: Dict[str, Any], *, instruction: str) -> Dict[str, Any]:
    h = hashlib.md5((ex["input"] or "").encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    return {
        "instruction": instruction,
        "input": ex["input"],
        "output": ex["output"],
        "domain": "insurance/acord_oos",
        "metadata": {
            "category": "oos",
            "oos_subtype": ex["category"],
            "oos": True,
            "base_doc_id": f"oos_{ex['category']}_{h}",
        },
    }
