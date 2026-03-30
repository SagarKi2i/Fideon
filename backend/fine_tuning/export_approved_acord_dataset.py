"""
Export approved ACORD extraction runs from Supabase into JSONL for SFT/QLoRA.

Split order (critical):
  1) Load base records (one row per approved run).
  2) Split train vs holdout by base_doc_id using FT_ACORD_HOLDOUT_RATIO.
  3) Append OOS examples: train split (+15), holdout (+5), never duplicated across splits.
  4) Prompt-augment and input-noise **train** only; holdout uses DEFAULT_INSTRUCTION only (1 row/base doc).
"""
from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import quote

import httpx

from app.core.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from fine_tuning.acord_prompt_augment import (
    DEFAULT_INSTRUCTION,
    apply_input_noise_variants,
    cap_rows,
    expand_instruction_variants,
)
from fine_tuning.acord_training_targets import build_sft_label_json
from fine_tuning.acord_form_pipeline.schema import normalize_label
from fine_tuning.oos_refusal_examples import OOS_HOLDOUT_EXAMPLES, OOS_TRAIN_EXAMPLES, to_sft_record


def build_training_jsonl_record(
    *,
    extracted_json: Any,
    raw_text: str,
    run_id: str,
    source_filename: str | None = None,
    target_precomputed: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    One JSONL object as written by export: instruction + input + six-field output + metadata.
    Use target_precomputed when build_sft_label_json was already computed (avoids duplicate work).
    """
    extracted_dict = extracted_json if isinstance(extracted_json, dict) else {}
    target = target_precomputed if target_precomputed is not None else build_sft_label_json(extracted_dict)
    bid = str(run_id)
    metadata = {
        "run_id": bid,
        "source_filename": source_filename or "",
        "base_doc_id": bid,
        "category": "in_domain",
    }
    return {
        "instruction": DEFAULT_INSTRUCTION,
        "input": raw_text,
        "output": json.dumps(target, ensure_ascii=False),
        "domain": "insurance/acord",
        "metadata": metadata,
    }


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_approved_runs(*, limit: int = 1000, run_id: str | None = None) -> List[Dict[str, Any]]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")

    base_select = "select=id,created_at,source_filename,form_type_detected,raw_text,extracted_json,overall_confidence,status"
    if run_id:
        rid = quote(run_id, safe="")
        # Must match bulk export: only approved runs (rejected/draft must not train).
        query = f"{base_select}&id=eq.{rid}&status=eq.approved&limit=1"
    else:
        query = f"{base_select}&status=eq.approved&limit={limit}&order=created_at.asc"
    url = f"{SUPABASE_URL}/rest/v1/acord_extraction_runs?{query}"
    with httpx.Client(timeout=60) as client:
        resp = client.get(url, headers=_headers())
    if resp.status_code >= 400:
        raise RuntimeError(resp.text)
    rows = resp.json()
    if not isinstance(rows, list):
        rows = []
    before = len(rows)
    rows = [r for r in rows if str(r.get("status") or "").strip().lower() == "approved"]
    skipped = before - len(rows)
    if skipped:
        print(f"[export] skipped {skipped} non-approved run(s) (safety filter)", flush=True)
    return rows


def to_sft_base_records(runs: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    out: List[Dict[str, Any]] = []
    stats: Dict[str, int] = {
        "total_runs": len(runs),
        "non_dict_extracted_json": 0,
        "normalized_changed": 0,
    }
    for r in runs:
        extracted = r.get("extracted_json") or {}
        extracted_dict = extracted if isinstance(extracted, dict) else {}
        if not isinstance(extracted, dict):
            stats["non_dict_extracted_json"] += 1
        raw_text = r.get("raw_text") or extracted_dict.get("raw_text") or ""
        target = build_sft_label_json(extracted_dict)
        legacy_flat = normalize_label(extracted_dict)
        if json.dumps(target, sort_keys=True) != json.dumps(legacy_flat, sort_keys=True):
            stats["normalized_changed"] += 1
        bid = str(r.get("id") or "")
        sample = build_training_jsonl_record(
            extracted_json=extracted_dict,
            raw_text=raw_text,
            run_id=bid,
            source_filename=r.get("source_filename"),
            target_precomputed=target,
        )
        out.append(sample)
    return out, stats


def split_base_train_holdout(
    base_records: List[Dict[str, Any]],
    *,
    ratio: float,
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """Split by base_doc_id before augmentation. Returns (train, holdout, holdout_n)."""
    if len(base_records) <= 1:
        return base_records, [], 0
    rnd = random.Random(seed)
    rows = base_records[:]
    rnd.shuffle(rows)
    holdout_n = max(1, int(round(len(rows) * ratio)))
    holdout_n = min(holdout_n, len(rows) - 1)
    holdout_base = rows[:holdout_n]
    train_base = rows[holdout_n:]
    ht_ids = {r["metadata"]["base_doc_id"] for r in holdout_base}
    tr_ids = {r["metadata"]["base_doc_id"] for r in train_base}
    overlap = ht_ids & tr_ids
    assert not overlap, f"base_doc_id overlap between train and holdout: {overlap}"
    return train_base, holdout_base, holdout_n


def build_export_payload(
    runs: List[Dict[str, Any]],
    *,
    augment: bool,
    input_noise: bool,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Returns (train_rows, holdout_rows, stats_dict)."""
    base_records, stats = to_sft_base_records(runs)
    ratio = float(os.getenv("FT_ACORD_HOLDOUT_RATIO", "0.1"))
    train_base, holdout_base, holdout_n = split_base_train_holdout(base_records, ratio=ratio)

    oos_train = [to_sft_record(ex, instruction=DEFAULT_INSTRUCTION) for ex in OOS_TRAIN_EXAMPLES]
    oos_holdout = [to_sft_record(ex, instruction=DEFAULT_INSTRUCTION) for ex in OOS_HOLDOUT_EXAMPLES]

    for ex in oos_holdout:
        assert (ex.get("metadata") or {}).get("category") == "oos"

    train_with_oos = train_base + oos_train
    holdout_with_oos = holdout_base + oos_holdout

    if augment:
        train_final = expand_instruction_variants(train_with_oos)
    else:
        train_final = train_with_oos

    if input_noise:
        train_final = apply_input_noise_variants(train_final)
    train_final = cap_rows(train_final)

    stats_out = {
        **stats,
        "split_base_train": len(train_base),
        "split_base_holdout": len(holdout_base),
        "holdout_n": holdout_n,
        "oos_train_added": len(oos_train),
        "oos_holdout_added": len(oos_holdout),
        "train_after_augment": len(train_final),
        "holdout_total": len(holdout_with_oos),
        "augment_prompts": augment,
        "input_noise_variants": input_noise,
    }
    return train_final, holdout_with_oos, stats_out


def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export approved ACORD runs to JSONL")
    parser.add_argument("--out", default="fine_tuning/data/approved_acord.jsonl", help="Training JSONL path")
    parser.add_argument("--holdout-out", default=None, help="Holdout JSONL (instruction rows); required for split export")
    parser.add_argument("--limit", type=int, default=1000, help="Max rows to export from Supabase")
    parser.add_argument("--run-id", default=None, help="Export a single run_id (must be approved)")
    parser.add_argument("--augment-prompts", action="store_true", help="Enable instruction augmentation on train split")
    parser.add_argument("--no-augment-prompts", action="store_true")
    parser.add_argument("--input-noise", action="store_true", help="Enable input noise on train split")
    parser.add_argument("--no-input-noise", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Compute stats and print logs; skip writing files")
    args = parser.parse_args()

    if args.no_augment_prompts:
        augment = False
    elif args.augment_prompts:
        augment = True
    else:
        augment = os.getenv("ACORD_EXPORT_AUGMENT_PROMPTS", "true").strip().lower() in {"1", "true", "yes", "on"}

    if args.no_input_noise:
        input_noise = False
    elif args.input_noise:
        input_noise = True
    else:
        input_noise = os.getenv("ACORD_EXPORT_INPUT_NOISE", "true").strip().lower() in {"1", "true", "yes", "on"}

    runs = fetch_approved_runs(limit=args.limit, run_id=args.run_id)
    train_rows, holdout_rows, st = build_export_payload(runs, augment=augment, input_noise=input_noise)

    base_n = st["total_runs"]
    print(f"[data] base_records={base_n}")
    print(
        f"[data] split_base_train={st['split_base_train']} split_base_holdout={st['split_base_holdout']} "
        f"train_after_augment={st['train_after_augment']}"
    )
    print(
        f"[data] oos_train_added={st['oos_train_added']} oos_holdout_added={st['oos_holdout_added']} "
        f"holdout_total={st['holdout_total']}"
    )
    print(f"[data] augment_prompts={st['augment_prompts']} input_noise_variants={st['input_noise_variants']}")

    if not args.dry_run:
        out_path = Path(args.out).resolve()
        write_jsonl(out_path, train_rows)
        print(f"Wrote {len(train_rows)} train rows to {out_path}")
        if args.holdout_out:
            hp = Path(args.holdout_out).resolve()
            write_jsonl(hp, holdout_rows)
            print(f"Wrote {len(holdout_rows)} holdout rows to {hp}")
    else:
        print("[dry-run] skip writing files")

    print(
        "[stats] normalized_changed={changed} non_dict_extracted_json={bad}".format(
            changed=st.get("normalized_changed", 0),
            bad=st.get("non_dict_extracted_json", 0),
        )
    )


if __name__ == "__main__":
    main()
