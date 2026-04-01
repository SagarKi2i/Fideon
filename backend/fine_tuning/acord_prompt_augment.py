"""
Instruction + input noise augmentation: same labels, varied prompts / OCR-like noise.
"""
from __future__ import annotations

import os
import random
from copy import deepcopy
from typing import Any, Dict, List

# Strong default aligned with extraction eval (no metadata/confidence in output).
DEFAULT_INSTRUCTION = (
    "You are an ACORD 125 form extraction specialist. Extract agency name, contact name, "
    "carrier, policy number, email, and phone into a single JSON object with exactly those keys. "
    "Copy values exactly from the document text. Never hallucinate. Return null for missing fields. "
    "Never include extraction metadata, pipeline fields, or confidence scores in the output."
)

ADDITIONAL_VARIANTS: List[str] = [
    "Extract only the insured and producer sections from this ACORD 125 form as JSON.",
    "From the ACORD 125 form below, extract policy information and carrier details only.",
    "Identify the named insureds and lines of business indicated in this form.",
    "Extract all available fields from this ACORD 125 commercial insurance application.",
]

INSTRUCTION_VARIANTS: List[str] = [
    DEFAULT_INSTRUCTION,
    "Extract ACORD 125 fields from this document. Return only valid JSON with keys: "
    "agency_name, contact_name, carrier, policy_number, email, phone.",
    "Parse the following insurance application form and return structured JSON for producer and policy "
    "contact fields only (six keys). Use null where not present in the text.",
    "Identify agency, contact, carrier, policy number, email, and phone in this ACORD form text. "
    "Output JSON only, no commentary.",
    "Extract insured/producer and policy carrier information from the document. "
    "Respond with JSON matching the six-field extraction schema; null for absent values.",
] + ADDITIONAL_VARIANTS

# Cap after all augmentation (env override)
MAX_AUGMENTED_ROWS = int(os.getenv("ACORD_EXPORT_MAX_ROWS", "300"))


def expand_instruction_variants(
    records: List[Dict[str, Any]],
    *,
    variants: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """One row per (record × instruction variant). OOS rows get the same variants."""
    use = variants if variants else INSTRUCTION_VARIANTS
    out: List[Dict[str, Any]] = []
    for rec in records:
        base_meta = dict(rec.get("metadata") or {})
        for i, instr in enumerate(use):
            row = deepcopy(rec)
            row["instruction"] = instr
            meta = dict(base_meta)
            meta["prompt_variant_index"] = i
            meta["augmentation"] = "instruction_variant"
            row["metadata"] = meta
            out.append(row)
    return out


def apply_input_noise_variants(
    records: List[Dict[str, Any]],
    *,
    seed: int = 42,
    p_strip: float = 0.3,
    p_trunc: float = 0.3,
    p_page_header: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Randomly apply OCR/formatting noise. Same output target; marks metadata.input_noise.
    Skips noise that would destroy very short OOS inputs.
    """
    out: List[Dict[str, Any]] = []
    for i, rec in enumerate(records):
        row = deepcopy(rec)
        rnd = random.Random(seed + i * 9973)
        meta = dict(row.get("metadata") or {})
        noises: List[str] = []
        text = str(row.get("input") or "")
        is_oos = bool(meta.get("oos")) or (row.get("domain") == "insurance/acord_oos")

        if len(text) > 10 and rnd.random() < p_strip:
            text = text.strip()
            noises.append("strip")
        if len(text) > 80 and rnd.random() < p_trunc:
            new_len = max(40, int(len(text) * 0.8))
            text = text[:new_len]
            noises.append("trunc80")
        if len(text) > 5 and rnd.random() < p_page_header:
            text = "PAGE 1 OF 3\n\n" + text
            noises.append("page_header")

        row["input"] = text
        if noises:
            meta["input_noise"] = noises
            meta["augmentation"] = (meta.get("augmentation") or "") + "+input_noise"
        row["metadata"] = meta
        out.append(row)
    return out


def cap_rows(records: List[Dict[str, Any]], max_rows: int | None = None) -> List[Dict[str, Any]]:
    cap = max_rows if max_rows is not None else MAX_AUGMENTED_ROWS
    if cap <= 0 or len(records) <= cap:
        return records
    return records[:cap]
