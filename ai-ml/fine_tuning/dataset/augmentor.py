"""
augmentor.py — data augmentation for insurance training samples.

Applies text-level augmentations to increase dataset diversity without
requiring new labelled documents:

  1. OCR noise  — realistic character substitutions (O↔0, l↔1, I↔1, etc.)
                  injected into the user-message OCR text.
  2. Field dropout — randomly blank non-required leaf fields in the assistant
                     JSON to teach robustness to partially-filled forms.
  3. Copy augmentation — produce N augmented copies per original sample.

Usage
-----
    from fine_tuning.dataset.augmentor import DataAugmentor, AugmentorConfig

    aug = DataAugmentor(AugmentorConfig(copies_per_sample=2, ocr_error_rate=0.02))
    augmented_rows = aug.augment_dataset(original_rows)
    final_rows = original_rows + augmented_rows
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional


# ── OCR confusion pairs (symmetric) ──────────────────────────────────────────

_OCR_PAIRS: List[tuple] = [
    ("0", "O"),
    ("1", "l"),
    ("1", "I"),
    ("5", "S"),
    ("8", "B"),
    ("6", "G"),
    ("2", "Z"),
]

# Fields that must never be blanked (training signal depends on them)
_REQUIRED_FIELD_NAMES: frozenset = frozenset({
    "policy_number",
    "named_insured",
    "document_type",
    "certificate_number",
    "effective_date",
    "expiration_date",
    "claim_number",
})


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class AugmentorConfig:
    ocr_error_rate: float = 0.02        # Fraction of chars to corrupt in OCR text
    field_dropout_rate: float = 0.10    # Fraction of non-required fields to blank
    copies_per_sample: int = 1          # Augmented copies to produce per sample
    seed: int = 42


# ── Augmentor ─────────────────────────────────────────────────────────────────

class DataAugmentor:
    def __init__(self, config: Optional[AugmentorConfig] = None) -> None:
        self._cfg = config or AugmentorConfig()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _ocr_noise(self, text: str, rng: random.Random) -> str:
        """Inject OCR-style character substitutions into *text*."""
        if not text or self._cfg.ocr_error_rate <= 0:
            return text
        chars = list(text)
        n_errors = max(1, int(len(chars) * self._cfg.ocr_error_rate))
        positions = rng.sample(range(len(chars)), min(n_errors, len(chars)))
        for pos in positions:
            c = chars[pos]
            for a, b in _OCR_PAIRS:
                if c == a and rng.random() < 0.5:
                    chars[pos] = b
                    break
                elif c == b and rng.random() < 0.5:
                    chars[pos] = a
                    break
        return "".join(chars)

    def _drop_fields(self, fields: Any, rng: random.Random, _depth: int = 0) -> Any:
        """Recursively blank a fraction of non-required leaf string fields."""
        if _depth > 8 or not isinstance(fields, dict):
            return fields
        result: Dict[str, Any] = {}
        for k, v in fields.items():
            if k in _REQUIRED_FIELD_NAMES:
                result[k] = v
            elif isinstance(v, dict):
                if set(v.keys()) <= {"value", "page", "confidence"}:
                    # {value, page, confidence} leaf — optionally blank the value
                    if isinstance(v.get("value"), str) and rng.random() < self._cfg.field_dropout_rate:
                        result[k] = {**v, "value": ""}
                    else:
                        result[k] = v
                else:
                    result[k] = self._drop_fields(v, rng, _depth + 1)
            elif isinstance(v, list):
                result[k] = [
                    self._drop_fields(item, rng, _depth + 1)
                    if isinstance(item, dict) else item
                    for item in v
                ]
            elif isinstance(v, str) and rng.random() < self._cfg.field_dropout_rate:
                result[k] = ""
            else:
                result[k] = v
        return result

    def _augment_one(self, row: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
        """Return one augmented copy of a chat-format training row."""
        messages: List[Dict[str, Any]] = []
        for msg in row.get("messages", []):
            role    = msg.get("role")
            content = msg.get("content", "")

            if role == "user":
                if isinstance(content, str):
                    content = self._ocr_noise(content, rng)
                elif isinstance(content, list):
                    # Multimodal list: apply noise only to text blocks
                    content = [
                        {**block, "text": self._ocr_noise(block["text"], rng)}
                        if block.get("type") == "text" else block
                        for block in content
                    ]
            elif role == "assistant" and isinstance(content, str):
                try:
                    fields = json.loads(content)
                    if isinstance(fields, dict):
                        fields  = self._drop_fields(fields, rng)
                        content = json.dumps(fields, ensure_ascii=False, indent=2)
                except (json.JSONDecodeError, TypeError):
                    pass

            messages.append({"role": role, "content": content})

        aug_row = dict(row)
        aug_row["messages"] = messages
        meta = dict(row.get("metadata") or {})
        meta["augmented"] = True
        aug_row["metadata"] = meta
        return aug_row

    # ── Public API ────────────────────────────────────────────────────────────

    def augment_dataset(
        self,
        rows: List[Dict[str, Any]],
        n_copies: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Produce augmented copies of *rows*.

        Returns only the NEW augmented rows (not the originals).
        Combine with originals in the caller:

            final = rows + augmentor.augment_dataset(rows)

        Parameters
        ----------
        rows    : Original chat-format training rows.
        n_copies: Augmented copies per original (default: config.copies_per_sample).
        """
        rng = random.Random(self._cfg.seed)
        copies = n_copies if n_copies is not None else self._cfg.copies_per_sample
        augmented: List[Dict[str, Any]] = []
        for row in rows:
            for _ in range(copies):
                augmented.append(self._augment_one(row, rng))
        return augmented
