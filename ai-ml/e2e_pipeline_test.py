#!/usr/bin/env python3
"""
END-TO-END PIPELINE TEST
========================
Tests the complete Fideon fine-tuning cycle without a GPU:

  STAGE 1 — EXTRACTION      : OCR text  ->  raw KV field dict
  STAGE 2 — USER CORRECTION : wrong fields + user fixes  ->  training sample
  STAGE 3 — LOCAL TRAINING  : version_store -> DatasetBuilder -> LF layout
                               version_registry pending -> promote
  STAGE 4 — RE-EXTRACTION   : parse trained assistant content -> field F1 = 1.0

Run from e:\\Fideon\\ai-ml\\:
    python e2e_pipeline_test.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List

# ── Path setup ─────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

# ── Mock fcntl (Windows) ───────────────────────────────────────────────────────
import types
_fcntl = types.ModuleType("fcntl")
_fcntl.LOCK_EX = 2; _fcntl.LOCK_NB = 4; _fcntl.LOCK_UN = 8
_fcntl.flock = lambda *a, **k: None
sys.modules.setdefault("fcntl", _fcntl)

# ── Mock transformers (no GPU / no install) ────────────────────────────────────
_tf_stub = types.ModuleType("transformers")
_tf_stub.PretrainedConfig = object
_tf_stub.PreTrainedConfig = object
_iu_stub = types.ModuleType("transformers.image_utils")
_iu_stub.VideoInput = list
sys.modules.setdefault("transformers", _tf_stub)
sys.modules.setdefault("transformers.image_utils", _iu_stub)


# ══════════════════════════════════════════════════════════════════════════════
# Reporting harness
# ══════════════════════════════════════════════════════════════════════════════

_STAGES = ["EXTRACTION", "CORRECTION", "TRAINING", "RE-EXTRACTION"]
_results: Dict[str, List[str]] = {s: [] for s in _STAGES}
_stage_failed: Dict[str, bool] = {s: False for s in _STAGES}

_SEP  = "=" * 70
_SEP2 = "-" * 70

def _ok(stage: str, msg: str) -> None:
    _results[stage].append(f"  [OK]   {msg}")

def _fail(stage: str, msg: str, exc: Exception | None = None) -> None:
    _stage_failed[stage] = True
    detail = f"\n         {type(exc).__name__}: {exc}" if exc else ""
    _results[stage].append(f"  [FAIL] {msg}{detail}")

def _check(stage: str, condition: bool, label: str, fail_msg: str = "") -> bool:
    if condition:
        _ok(stage, label)
        return True
    _fail(stage, fail_msg or label)
    return False

def _print_stage(stage: str) -> None:
    status = "FAILED" if _stage_failed[stage] else "PASSED"
    print(f"\n{_SEP2}")
    print(f"  STAGE: {stage}  [{status}]")
    print(_SEP2)
    for line in _results[stage]:
        print(line)


# ══════════════════════════════════════════════════════════════════════════════
# Shared test fixture — realistic ACORD 25 Certificate of Insurance
# ══════════════════════════════════════════════════════════════════════════════

# Simulates Surya OCR output from a scanned ACORD 25 document.
# Several fields intentionally have OCR errors matching real-world mistakes.
ACORD25_OCR_TEXT = (
    "CERTIFICATE OF LIABILITY INSURANCE\n"
    "DATE (MM/DD/YYYY): 01/15/2026\n"
    "PRODUCER: Highpoint Insurance Agency LLC\n"
    "ADDRESS: 4500 Oak Street, Chicago, IL 60601\n"
    "PHONE (A/C, No, Ext): (312) 555-0198    FAX (A/C, No): (312) 555-0199\n"
    "E-MAIL ADDRESS: certs@highpoint-ins.com\n"
    "INSURER(S) AFFORDING COVERAGE    NAIC #\n"
    "INSURED    Bridgewater Manufacturing Inc.\n"
    "ADDRESS    2100 Industrial Blvd, Detroit, MI 48201\n"
    "INSURER A: Hartford Fire Insurance Co    NAIC: 19682\n"
    "INSURER B: Zurich American Insurance    NAIC: 16535\n"
    "CERTIFICATE NUMBER: CERT-2026-00I42\n"
    "REVISION NUMBER: 3\n"
    "COVERAGES CERTIFICATE NUMBER: CERT-2026-00142\n"
    "TYPE OF INSURANCE: COMMERCIAL GENERAL LIABILITY\n"
    "POLICY NUMBER: HFI-GL-20260115-9987\n"
    "POLICY EFF: 01/15/2026    POLICY EXP: 01/15/2027\n"
    "EACH OCCURRENCE: $ 1,000,000\n"
    "DAMAGE TO RENTED PREMISES: $ 100,000\n"
    "MED EXP (Any one person): $ 5,000\n"
    "PERSONAL & ADV INJURY: $ 1,000,000\n"
    "GENERAL AGGREGATE: $ 2,000,000\n"
    "PRODUCTS - COMP/OP AGG: $ 2,000,000\n"
    "TYPE OF INSURANCE: AUTOMOBILE LIABILITY\n"
    "POLICY NUMBER: HFI-AU-20260115-3341\n"
    "COMBINED SINGLE LIMIT: $ 1,000,000\n"
    "TYPE OF INSURANCE: WORKERS COMPENSATION\n"
    "POLICY NUMBER: ZUR-WC-20260115-7721\n"
    "E.L. EACH ACCIDENT: $ 500,000\n"
    "E.L. DISEASE - EA EMPLOYEE: $ 500,000\n"
    "E.L. DISEASE - POLICY LIMIT: $ 500,000\n"
    "CERTIFICATE HOLDER\n"
    "First National Bank of Detroit\n"
    "999 Woodward Avenue, Detroit, MI 48226\n"
    "DESCRIPTION OF OPERATIONS: General contracting operations at all owned\n"
    "and leased locations. Additional insured per ISO CG 20 10.\n"
    "AUTHORIZED REPRESENTATIVE: James R. Whitmore\n"
)

# What the model WRONGLY extracted initially (simulating real extraction errors)
ACORD25_ORIGINAL_WRONG = {
    "date":                   "01/15/2026",          # correct
    "producer":               "Highpoint Insurance Agency LLC",  # correct
    "producer_address":       "4500 Oak Street Chicago IL 60601",  # missing comma formatting
    "producer_phone":         "(312) 555-0198",       # correct
    "insured_name":           "Bridgewater Manufacturing Inc",    # missing period
    "insured_address":        "2100 Industrial Blvd Detroit MI",  # missing zip + comma
    "insurer_a":              "Hartford Fire Insurance Co",        # correct
    "insurer_a_naic":         "19682",                # correct
    "insurer_b":              "Zurich American Insurance",         # correct
    "insurer_b_naic":         "16535",                # correct
    "certificate_number":     "CERT-2026-00I42",      # OCR error: I instead of 1
    "revision_number":        "3",                    # correct
    "gl_policy_number":       "HFI-GL-20260115-9987", # correct
    "gl_policy_eff":          "01/15/2026",           # correct
    "gl_policy_exp":          "01/15/2027",           # correct
    "gl_each_occurrence":     "1000000",              # missing $ and commas
    "gl_general_aggregate":   "2000000",              # missing $ and commas
    "auto_policy_number":     "HFI-AU-20260115-3341", # correct
    "auto_csl":               "1000000",              # missing $ and commas
    "wc_policy_number":       "ZUR-WC-20260115-7721", # correct
    "wc_el_each_accident":    "500000",               # missing $ and commas
    "certificate_holder":     "First National Bank of Detroit",   # correct
    "certificate_holder_address": "999 Woodward Avenue Detroit MI",  # missing zip + comma
    "description_of_operations": "General contracting operations",  # truncated
    "authorized_representative": "James R. Whitmore",               # correct
}

# User corrections — only the wrong/incomplete fields
ACORD25_CORRECTIONS = {
    "producer_address":           "4500 Oak Street, Chicago, IL 60601",
    "insured_name":               "Bridgewater Manufacturing Inc.",
    "insured_address":            "2100 Industrial Blvd, Detroit, MI 48201",
    "certificate_number":         "CERT-2026-00142",        # fixed OCR: I -> 1
    "gl_each_occurrence":         "$1,000,000",
    "gl_general_aggregate":       "$2,000,000",
    "auto_csl":                   "$1,000,000",
    "wc_el_each_accident":        "$500,000",
    "certificate_holder_address": "999 Woodward Avenue, Detroit, MI 48226",
    "description_of_operations":  (
        "General contracting operations at all owned and leased locations. "
        "Additional insured per ISO CG 20 10."
    ),
}

# What the fully-correct extraction should look like (original + corrections merged)
ACORD25_EXPECTED_FINAL = {**ACORD25_ORIGINAL_WRONG, **ACORD25_CORRECTIONS}


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — EXTRACTION
#   Simulates: Surya OCR runs on the PDF -> _extract_kv_from_ocr_text() runs
#   Output: raw key-value dict
# ══════════════════════════════════════════════════════════════════════════════

print(f"\n{_SEP}")
print("  STAGE 1 — EXTRACTION")
print(_SEP)

try:
    from extractor import _extract_kv_from_ocr_text
    kv = _extract_kv_from_ocr_text(ACORD25_OCR_TEXT)

    _check("EXTRACTION", isinstance(kv, dict) and len(kv) > 0,
           f"KV extractor returned {len(kv)} fields from OCR text",
           "KV extractor returned empty dict")

    _check("EXTRACTION", kv.get("producer") == "Highpoint Insurance Agency LLC",
           "producer name extracted",
           f"producer wrong: {kv.get('producer')!r}")

    _check("EXTRACTION", kv.get("insurer_a_naic") == "19682" or kv.get("naic") == "19682"
           or any("19682" in str(v) for v in kv.values()),
           "NAIC code 19682 found in extracted KV",
           f"NAIC code missing from extraction. Keys: {list(kv.keys())[:10]}")

    _check("EXTRACTION", kv.get("policy_number") is not None or kv.get("gl_policy_number") is not None
           or any("HFI-GL" in str(v) for v in kv.values()),
           "GL policy number extracted from multi-column OCR line",
           "GL policy number not found in extraction")

    _check("EXTRACTION", kv.get("certificate_number") is not None
           or any("CERT-2026" in str(v) for v in kv.values()),
           "certificate number extracted (may contain OCR error I->1)",
           "certificate number not found")

    _check("EXTRACTION", not any(k.strip("_").isdigit() for k in kv),
           "no purely-numeric keys in extracted KV",
           "numeric-only keys leaked into extraction")

    print(f"\n  Extracted {len(kv)} fields. Sample:")
    for k, v in list(kv.items())[:6]:
        print(f"    {k}: {v!r}")

except Exception as exc:
    _fail("EXTRACTION", "Unexpected exception in extraction stage", exc)
    traceback.print_exc()

_print_stage("EXTRACTION")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — USER CORRECTION
#   Simulates: user reviews wrong fields in the UI and submits corrections
#   build_training_sample_from_correction() merges and formats the sample
# ══════════════════════════════════════════════════════════════════════════════

print(f"\n{_SEP}")
print("  STAGE 2 — USER CORRECTION")
print(_SEP)

sample = None
corrected_fields_from_sample = None

try:
    from fine_tuning.continuous_learning.ingest import (
        build_training_sample_from_correction,
        get_universal_system_prompt,
        get_corrected_paths,
    )
    from fine_tuning.dataset.dataset_builder import (
        validate_chat_format,
        parse_assistant_fields,
    )
    from insurance_schema_registry import get_registry

    sample = build_training_sample_from_correction(
        run_row={
            "form_type":        "25",
            "raw_text":         ACORD25_OCR_TEXT,
            "original_fields":  ACORD25_ORIGINAL_WRONG,
            "upload_id":        "e2e-upload-acord25-001",
            "sample_id":        "e2e-sample-acord25-001",
        },
        corrected_json=ACORD25_CORRECTIONS,
    )

    msgs = sample.get("messages", [])

    # ── Structure checks ──────────────────────────────────────────────────────
    _check("CORRECTION", len(msgs) == 3,
           "training sample has 3 messages (system / user / assistant)",
           f"expected 3 messages, got {len(msgs)}")

    _check("CORRECTION", msgs[0]["role"] == "system" and
           msgs[0]["content"] == get_universal_system_prompt(),
           "system message matches get_universal_system_prompt()",
           "system message content mismatch")

    _check("CORRECTION", msgs[1]["role"] == "user" and
           "ACORD Form 25" in msgs[1]["content"],
           "user message contains 'ACORD Form 25' label",
           f"ACORD Form 25 label missing from user content")

    _check("CORRECTION", "Bridgewater Manufacturing" in msgs[1]["content"],
           "user message contains OCR text (insured name visible)",
           "OCR text not forwarded to user message")

    _check("CORRECTION", "CERT-2026" in msgs[1]["content"],
           "certificate number visible in user OCR text",
           "certificate number absent from user content")

    # ── Assistant content checks ──────────────────────────────────────────────
    assistant_content = msgs[2]["content"] if len(msgs) > 2 else ""
    _check("CORRECTION", assistant_content.startswith("FIELDS:"),
           "assistant content uses new FIELDS: format",
           f"assistant content format wrong: {assistant_content[:60]!r}")

    corrected_fields_from_sample = parse_assistant_fields(assistant_content)
    _check("CORRECTION", corrected_fields_from_sample is not None,
           "parse_assistant_fields() successfully parses assistant content",
           "parse_assistant_fields() returned None — assistant content malformed")

    if corrected_fields_from_sample:
        # Corrections must be applied
        for field, expected_val in ACORD25_CORRECTIONS.items():
            actual = corrected_fields_from_sample.get(field)
            _check("CORRECTION", actual == expected_val,
                   f"correction applied: {field} = {expected_val!r}",
                   f"correction NOT applied: {field} expected {expected_val!r}, got {actual!r}")

        # Uncorrected fields must survive from original
        for field in ["producer", "insurer_a", "insurer_b_naic", "gl_policy_number",
                      "certificate_holder", "authorized_representative"]:
            original_val = ACORD25_ORIGINAL_WRONG.get(field)
            actual_val   = corrected_fields_from_sample.get(field)
            _check("CORRECTION", actual_val == original_val,
                   f"uncorrected field preserved: {field} = {original_val!r}",
                   f"field lost: {field} expected {original_val!r}, got {actual_val!r}")

    # ── Corrected paths ───────────────────────────────────────────────────────
    corrected_paths = get_corrected_paths(ACORD25_ORIGINAL_WRONG, ACORD25_CORRECTIONS)
    _check("CORRECTION", "certificate_number" in corrected_paths,
           f"get_corrected_paths() found {len(corrected_paths)} corrected fields",
           "get_corrected_paths() missed certificate_number correction")

    # ── Metadata ──────────────────────────────────────────────────────────────
    meta = sample.get("metadata", {})
    _check("CORRECTION", meta.get("document_type") == "25",
           "metadata.document_type = '25'",
           f"metadata.document_type wrong: {meta.get('document_type')!r}")
    _check("CORRECTION", meta.get("upload_id") == "e2e-upload-acord25-001",
           "metadata.upload_id preserved",
           f"upload_id wrong: {meta.get('upload_id')!r}")
    _check("CORRECTION", sample.get("domain") == "insurance",
           "domain = 'insurance'",
           f"domain wrong: {sample.get('domain')!r}")

    # ── validate_chat_format must pass ────────────────────────────────────────
    try:
        validate_chat_format(sample, 0)
        _ok("CORRECTION", "validate_chat_format() passed — sample is training-ready")
    except Exception as exc:
        _fail("CORRECTION", "validate_chat_format() raised", exc)

    print(f"\n  Corrected {len(corrected_paths)} field(s): {corrected_paths}")

except Exception as exc:
    _fail("CORRECTION", "Unexpected exception in correction stage", exc)
    traceback.print_exc()

_print_stage("CORRECTION")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — LOCAL TRAINING (data pipeline — no GPU needed)
#   Simulates:
#     a) version_store.append_training_sample() x threshold -> snapshot
#     b) DatasetBuilder.build() -> train.jsonl + LLaMA-Factory data/ layout
#     c) _dict_to_yaml() -> training config YAML
#     d) version_registry pending -> promote (simulates job completing)
# ══════════════════════════════════════════════════════════════════════════════

print(f"\n{_SEP}")
print("  STAGE 3 — LOCAL TRAINING  (data pipeline)")
print(_SEP)

_train_jsonl_path = None

try:
    with tempfile.TemporaryDirectory() as _tmp:
        tmp = Path(_tmp)

        from fine_tuning.continuous_learning.version_store import (
            append_training_sample,
            load_all_versioned_rows,
            load_pending_rows,
        )
        from fine_tuning.dataset.dataset_builder import DatasetBuilder
        from fine_tuning.registry.version_registry import VersionRegistry
        from fine_tuning.train import _dict_to_yaml, USE_LLAMA_FACTORY

        # ── 3a. version_store: push samples -> snapshot ───────────────────────
        # Push the E2E sample (from Stage 2) plus 2 more synthetic rows to hit
        # threshold=3 and trigger a snapshot automatically.
        THRESHOLD = 3
        rows_to_push = [sample] if sample else []

        # Build 2 additional correction samples to reach threshold
        from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
        for i, (form, field, wrong, right) in enumerate([
            ("POLICY_DEC", "policy_number", "POL-2O26-001", "POL-2026-001"),
            ("CERTIFICATE", "certificate_number", "CERT-OO1", "CERT-001"),
        ]):
            rows_to_push.append(build_training_sample_from_correction(
                run_row={
                    "form_type":       form,
                    "raw_text":        f"Policy Number: {right}\nInsured: Test Corp {i}",
                    "original_fields": {field: wrong},
                    "upload_id":       f"e2e-uid-{i}",
                    "sample_id":       f"e2e-sid-{i}",
                },
                corrected_json={field: right},
            ))

        snapshot_outcome = None
        for idx, row in enumerate(rows_to_push):
            outcome = append_training_sample(tmp, row, retrain_threshold=THRESHOLD)
            if outcome.version_snapshot_path is not None:
                snapshot_outcome = outcome

        _check("TRAINING", snapshot_outcome is not None,
               f"version_store: snapshot created after {THRESHOLD} rows",
               f"snapshot not created — threshold={THRESHOLD}, pushed={len(rows_to_push)}")

        if snapshot_outcome:
            _check("TRAINING", snapshot_outcome.snapshot_version == 1,
                   "first snapshot is version 1",
                   f"snapshot_version = {snapshot_outcome.snapshot_version}")
            _check("TRAINING", load_pending_rows(tmp) == [],
                   "pending queue cleared after snapshot promotion",
                   "pending rows still present after snapshot")
            versioned = load_all_versioned_rows(tmp)
            _check("TRAINING", len(versioned) == THRESHOLD,
                   f"{THRESHOLD} versioned rows available for DatasetBuilder",
                   f"expected {THRESHOLD} versioned rows, got {len(versioned)}")

        # ── 3b. DatasetBuilder: train.jsonl + LLaMA-Factory data/ layout ──────
        cfg = {
            "paths": {
                "datasets_dir":  str(tmp / "datasets"),
                "runs_dir":      str(tmp / "runs"),
                "registry_path": str(tmp / "registry.json"),
            },
            "continuous_learning": {
                "feedback_datasets_dir": str(tmp / "feedback"),
            },
        }

        snapshot_path = snapshot_outcome.version_snapshot_path if snapshot_outcome else None
        if not snapshot_path:
            # Fallback: write a minimal snapshot from rows_to_push
            snapshot_path = str(tmp / "fallback_snapshot.jsonl")
            Path(snapshot_path).write_text(
                "\n".join(json.dumps(r) for r in rows_to_push) + "\n", encoding="utf-8"
            )

        build_result = DatasetBuilder(cfg).build(
            new_data_path=snapshot_path,
            cycle_id="e2e-cycle-001",
            min_records=1,
        )

        train_path = Path(build_result.train_jsonl_path)
        _check("TRAINING", train_path.exists(),
               f"train.jsonl written to {train_path}",
               "train.jsonl file not found")

        _check("TRAINING", build_result.new_records == THRESHOLD,
               f"DatasetBuilder: {THRESHOLD} new records in dataset",
               f"DatasetBuilder: new_records={build_result.new_records}, expected {THRESHOLD}")

        _check("TRAINING", build_result.rejected_records == 0,
               "0 records rejected (all samples valid chat format)",
               f"{build_result.rejected_records} records rejected")

        _check("TRAINING", len(build_result.fingerprint) == 64,
               f"SHA-256 fingerprint computed: {build_result.fingerprint[:16]}...",
               "fingerprint length wrong")

        # Verify LLaMA-Factory data/ layout
        lf_data_dir = train_path.parent / "data"
        _check("TRAINING", lf_data_dir.exists(),
               "LLaMA-Factory data/ directory created",
               f"data/ directory missing at {lf_data_dir}")
        _check("TRAINING", (lf_data_dir / "train.jsonl").exists(),
               "data/train.jsonl written for LLaMA-Factory",
               "data/train.jsonl missing")
        _check("TRAINING", (lf_data_dir / "dataset_info.json").exists(),
               "data/dataset_info.json written",
               "data/dataset_info.json missing")

        # Verify dataset_info.json content
        ds_info = json.loads((lf_data_dir / "dataset_info.json").read_text())
        _check("TRAINING", "fideon_insurance" in ds_info,
               "dataset_info.json has 'fideon_insurance' key",
               f"dataset_info.json missing fideon_insurance key: {list(ds_info.keys())}")
        _check("TRAINING", ds_info.get("fideon_insurance", {}).get("formatting") == "sharegpt",
               "formatting=sharegpt in dataset_info.json",
               "formatting field wrong in dataset_info.json")

        # Verify train.jsonl is parseable and has correct structure
        train_rows = [json.loads(l) for l in train_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        _check("TRAINING", len(train_rows) >= THRESHOLD,
               f"train.jsonl contains {len(train_rows)} rows (>= {THRESHOLD})",
               f"train.jsonl has too few rows: {len(train_rows)}")
        _check("TRAINING", all("messages" in r for r in train_rows),
               "every row in train.jsonl has 'messages' key",
               "some rows in train.jsonl missing 'messages' key")

        # ── 3c. _dict_to_yaml: training config generation ─────────────────────
        lf_config = {
            "model_name_or_path": "/workspace/models/qwen2-vl-7b",
            "stage":              "sft",
            "do_train":           True,
            "finetuning_type":    "lora",
            "lora_rank":          16,
            "lora_alpha":         32.0,
            "lora_dropout":       0.05,
            "lora_target":        "all",
            "visual_inputs":      True,
            "template":           "qwen2_vl",
            "dataset":            "fideon_insurance",
            "dataset_dir":        str(lf_data_dir),
            "output_dir":         str(tmp / "adapter_output"),
            "num_train_epochs":   3,
            "per_device_train_batch_size": 1,
            "learning_rate":      2e-5,
            "fp16":               False,
            "bf16":               True,
            "quantization_bit":   4,
            "flash_attn":         "fa2",
        }
        yaml_str = _dict_to_yaml(lf_config)

        _check("TRAINING", "model_name_or_path:" in yaml_str,
               "_dict_to_yaml: model_name_or_path present in config",
               "_dict_to_yaml: model_name_or_path missing")
        _check("TRAINING", "visual_inputs: true" in yaml_str,
               "_dict_to_yaml: visual_inputs=true (Qwen2-VL multimodal enabled)",
               "_dict_to_yaml: visual_inputs missing or wrong")
        _check("TRAINING", "template: qwen2_vl" in yaml_str,
               "_dict_to_yaml: template=qwen2_vl",
               "_dict_to_yaml: template wrong")
        _check("TRAINING", "quantization_bit: 4" in yaml_str,
               "_dict_to_yaml: QLoRA 4-bit quantization in config",
               "_dict_to_yaml: quantization_bit missing")
        _check("TRAINING", "bf16: true" in yaml_str,
               "_dict_to_yaml: bf16=true (bfloat16 training)",
               "_dict_to_yaml: bf16 wrong")
        _check("TRAINING", f"dataset_dir:" in yaml_str,
               "_dict_to_yaml: dataset_dir present",
               "_dict_to_yaml: dataset_dir missing")

        print(f"\n  Backend: {'LLaMA-Factory CLI' if USE_LLAMA_FACTORY else 'HuggingFace Trainer (fallback)'}")
        print(f"  Set USE_LLAMA_FACTORY=1 on RunPod to use LLaMA-Factory.")

        # ── 3d. version_registry: pending -> promote ──────────────────────────
        reg = VersionRegistry(str(tmp / "version_registry.json"))

        _check("TRAINING", reg.get_current_version() == 0,
               "version_registry starts at v0",
               f"starting version wrong: {reg.get_current_version()}")

        v = reg.create_pending_entry(
            cycle_id="e2e-cycle-001",
            job_id="e2e-job-001",
            parent_version=0,
            replay_fraction=0.20,
            checkpoint_dir=str(tmp / "checkpoint"),
        )
        _check("TRAINING", v == 1,
               "create_pending_entry() returns version 1",
               f"pending version = {v}")

        # Simulate training completing: promote with realistic eval scores
        reg.promote_version(
            version=v,
            merged_model_path=str(tmp / "merged_model"),
            adapter_path=str(tmp / "adapter"),
            eval_scores={"field_f1": 0.91, "field_recall": 0.89, "field_precision": 0.93},
            training_meta={
                "backend": "llamafactory" if USE_LLAMA_FACTORY else "qlora_hf",
                "job_id":  "e2e-job-001",
                "epochs":  3,
            },
        )

        _check("TRAINING", reg.get_current_version() == 1,
               "version_registry promoted to v1",
               f"current_version = {reg.get_current_version()}")
        _check("TRAINING", reg.get_current_base() == str(tmp / "merged_model"),
               "version_registry current_base points to merged model path",
               f"current_base wrong: {reg.get_current_base()!r}")

        versions = reg.list_versions()
        _check("TRAINING", len(versions) == 1 and versions[0]["status"] == "promoted",
               "version_registry shows status=promoted with eval scores",
               f"version status wrong: {versions[0].get('status') if versions else 'none'}")

        _check("TRAINING", versions[0]["eval_scores"]["field_f1"] == 0.91,
               "eval scores persisted in version_registry (f1=0.91)",
               "eval scores not saved correctly")

        _train_jsonl_path = str(train_path)

except Exception as exc:
    _fail("TRAINING", "Unexpected exception in training stage", exc)
    traceback.print_exc()

_print_stage("TRAINING")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4 — RE-EXTRACTION EVAL
#   Simulates: after training, the model sees the same OCR text and produces
#   the corrected fields. We verify the training sample teaches F1 = 1.0.
#
#   GPU not available locally — we prove the training DATA is correct by:
#     1. Taking the exact assistant content from Stage 2 (what the model is trained to output)
#     2. Parsing it with parse_assistant_fields()
#     3. Computing _field_scores(predicted, expected) -> F1 = 1.0
#     4. Running schema_registry.validate() on the output
#     5. Verifying eval_gate correctly processes the LocalEvalResult
# ══════════════════════════════════════════════════════════════════════════════

print(f"\n{_SEP}")
print("  STAGE 4 — RE-EXTRACTION EVAL  (training-data correctness proof)")
print(_SEP)

try:
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields
    from fine_tuning.evaluation.local_metrics import _field_scores
    from fine_tuning.evaluation.eval_gate import run_eval_gate
    from fine_tuning.evaluation.local_metrics import LocalEvalResult
    from insurance_schema_registry import get_registry

    # ── 4a. Simulate model output = assistant content from training sample ─────
    # After training on the correction, the model should produce exactly
    # what's in the assistant turn. Parse it to simulate re-extraction.
    if sample is None:
        _fail("RE-EXTRACTION", "No training sample from Stage 2 — skipping")
    else:
        assistant_content = sample["messages"][2]["content"]
        predicted = parse_assistant_fields(assistant_content)

        _check("RE-EXTRACTION", predicted is not None,
               "parse_assistant_fields() successfully parses training sample output",
               "parse_assistant_fields() returned None — content unparseable")

        if predicted is not None:
            # ── 4b. Recall vs corrections ─────────────────────────────────────
            # The model outputs ALL fields (original + corrections merged), so
            # precision vs the corrections-only subset will always be low by design.
            # The correct check is recall = 1.0: every corrected field appears in output.
            scores_vs_corrections = _field_scores(predicted, ACORD25_CORRECTIONS)
            rec_corr  = scores_vs_corrections["recall"]

            _check("RE-EXTRACTION", rec_corr == 1.0,
                   f"Recall = {rec_corr:.3f}  vs corrected fields "
                   f"(all {len(ACORD25_CORRECTIONS)} corrections present in model output)",
                   f"Recall < 1.0: {rec_corr:.3f} — not all corrections appear in output")

            # ── 4c. F1 vs full expected output ────────────────────────────────
            # The gold standard: predicted must match ALL 25 expected fields (F1=1.0).
            # This proves: original fields preserved AND corrections applied.
            scores_vs_full = _field_scores(predicted, ACORD25_EXPECTED_FINAL)
            f1_full  = scores_vs_full["f1"]
            rec_full = scores_vs_full["recall"]
            pre_full = scores_vs_full["precision"]

            _check("RE-EXTRACTION", f1_full == 1.0,
                   f"F1        = {f1_full:.3f}  vs FULL expected ({len(ACORD25_EXPECTED_FINAL)} fields) — perfect score",
                   f"F1 < 1.0 vs full expected: {f1_full:.3f}  — some original fields lost")
            _check("RE-EXTRACTION", rec_full == 1.0,
                   f"Recall    = {rec_full:.3f}  vs FULL expected (no expected field missing)",
                   f"Recall < 1.0 vs full: {rec_full:.3f}")
            _check("RE-EXTRACTION", pre_full == 1.0,
                   f"Precision = {pre_full:.3f}  vs FULL expected (no extra fields invented)",
                   f"Precision < 1.0 vs full: {pre_full:.3f}")

            # ── 4d. Specific field value accuracy ─────────────────────────────
            field_checks = [
                ("certificate_number",         "CERT-2026-00142",    "OCR error I->1 corrected"),
                ("gl_each_occurrence",         "$1,000,000",         "GL limit formatted correctly"),
                ("gl_general_aggregate",       "$2,000,000",         "GL aggregate formatted correctly"),
                ("auto_csl",                   "$1,000,000",         "Auto CSL formatted correctly"),
                ("wc_el_each_accident",        "$500,000",           "WC limit formatted correctly"),
                ("insured_name",               "Bridgewater Manufacturing Inc.", "insured name corrected"),
                ("producer",                   "Highpoint Insurance Agency LLC", "producer preserved"),
                ("insurer_a_naic",             "19682",              "NAIC code preserved"),
                ("certificate_holder",         "First National Bank of Detroit", "cert holder preserved"),
                ("authorized_representative",  "James R. Whitmore",  "authorized rep preserved"),
            ]
            for field, expected_val, label in field_checks:
                actual_val = predicted.get(field)
                _check("RE-EXTRACTION",
                       actual_val == expected_val,
                       f"{label}: {field} = {expected_val!r}",
                       f"{label} WRONG: {field} expected {expected_val!r}, got {actual_val!r}")

            # ── 4e. Schema registry validation of output ──────────────────────
            # The flat training dict won't pass schema (no document_identification/parties
            # sections) — that's expected for correction-style training data.
            # We validate that the registry runs without crashing and gives a result.
            registry = get_registry()
            val_result = registry.validate(predicted)
            _check("RE-EXTRACTION", isinstance(val_result, dict) and "valid" in val_result,
                   "schema_registry.validate() ran without error on re-extracted output",
                   "schema_registry.validate() crashed or returned wrong type")

            _check("RE-EXTRACTION", "errors" in val_result and "warnings" in val_result,
                   "validation result has 'errors' and 'warnings' keys",
                   "validation result missing required keys")

            # ── 4f. Eval gate: simulate passing gate with real scores ──────────
            # Simulate a LocalEvalResult as if we had run the model
            sim_eval = LocalEvalResult(
                field_f1=f1_full,
                field_recall=scores_vs_full["recall"],
                field_precision=scores_vs_full["precision"],
                n_examples=1,
                skipped=False,
            )
            eval_config = {
                "evaluation": {
                    "allow_skip_eval_gate": False,
                    "absolute_floors": {
                        "field_f1":     0.65,
                        "field_recall": 0.60,
                    },
                }
            }
            gate_result = run_eval_gate(sim_eval, None, None, eval_config, None)

            _check("RE-EXTRACTION", gate_result.passed is True,
                   f"eval_gate PASSED with f1={f1_full:.3f} (floor=0.65)",
                   f"eval_gate FAILED: {gate_result.failures}")

            _check("RE-EXTRACTION", gate_result.failures == [],
                   "eval_gate has no failure reasons",
                   f"eval_gate failures: {gate_result.failures}")

            print(f"\n  Re-extraction field accuracy summary:")
            print(f"    Recall    (vs corrections only)  : {rec_corr:.3f}")
            print(f"    F1        (vs full expected)      : {f1_full:.3f}")
            print(f"    Recall    (vs full expected)      : {rec_full:.3f}")
            print(f"    Precision (vs full expected)      : {pre_full:.3f}")
            print(f"    Fields in prediction              : {len(predicted)}")
            print(f"    Fields expected (full)            : {len(ACORD25_EXPECTED_FINAL)}")

except Exception as exc:
    _fail("RE-EXTRACTION", "Unexpected exception in re-extraction stage", exc)
    traceback.print_exc()

_print_stage("RE-EXTRACTION")


# ══════════════════════════════════════════════════════════════════════════════
# FINAL VERDICT
# ══════════════════════════════════════════════════════════════════════════════

print(f"\n{_SEP}")
print("  FINAL VERDICT")
print(_SEP)

total_checks = sum(len(v) for v in _results.values())
total_fails  = sum(
    sum(1 for line in v if line.startswith("  [FAIL]"))
    for v in _results.values()
)
total_pass   = total_checks - total_fails

for stage in _STAGES:
    stage_fails = sum(1 for line in _results[stage] if line.startswith("  [FAIL]"))
    stage_pass  = len(_results[stage]) - stage_fails
    status = "PASSED" if not _stage_failed[stage] else "FAILED"
    print(f"  {status:6}  Stage {stage:<16}  {stage_pass}/{len(_results[stage])} checks")

print(_SEP2)
if total_fails == 0:
    print(f"  ALL {total_pass}/{total_checks} CHECKS PASSED")
    print(f"  Pipeline: Extraction -> Correction -> Training -> Re-Extraction = 100%")
else:
    print(f"  {total_pass}/{total_checks} checks passed   |   {total_fails} FAILED")
    print(f"  Pipeline has {total_fails} issue(s) to fix before RunPod deployment.")
print(_SEP)

sys.exit(0 if total_fails == 0 else 1)
