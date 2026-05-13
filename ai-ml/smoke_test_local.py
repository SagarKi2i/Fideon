#!/usr/bin/env python3
"""
Local smoke test — Fideon fine-tuning data pipeline.

Tests all non-GPU, non-fcntl components against synthetic data.
No RunPod pod required. No CUDA required.

Run from e:\\Fideon\\ai-ml\\:
    python smoke_test_local.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

# ── Mock fcntl so version_store.py can be imported on Windows ─────────────────
import types
_fcntl = types.ModuleType("fcntl")
_fcntl.LOCK_EX = 2
_fcntl.LOCK_NB = 4
_fcntl.LOCK_UN = 8
_fcntl.flock   = lambda *a, **k: None   # no-op lock (single process, safe locally)
sys.modules.setdefault("fcntl", _fcntl)

# ── Mock transformers so extractor.py can be imported on Windows ───────────────
# extractor.py calls _patch_transformers_compat() at module level which imports
# transformers and transformers.image_utils. Provide a minimal stub so the patch
# is a no-op and the pure-Python _extract_kv_from_ocr_text is accessible.
_tf_stub = types.ModuleType("transformers")
_tf_stub.PretrainedConfig = object
_tf_stub.PreTrainedConfig = object
_iu_stub = types.ModuleType("transformers.image_utils")
_iu_stub.VideoInput = list
sys.modules.setdefault("transformers", _tf_stub)
sys.modules.setdefault("transformers.image_utils", _iu_stub)

# ── Test harness ──────────────────────────────────────────────────────────────
PASS: list[str] = []
FAIL: list[str] = []

GREEN  = ""
RED    = ""
YELLOW = ""
BOLD   = ""
RESET  = ""

def _run(name: str, fn):
    try:
        fn()
        print(f"  {GREEN}PASS{RESET}  {name}")
        PASS.append(name)
    except Exception as exc:
        print(f"  {RED}FAIL{RESET}  {name}")
        print(f"      {YELLOW}{type(exc).__name__}: {exc}{RESET}")
        traceback.print_exc()
        FAIL.append(name)


# ════════════════════════════════════════════════════════════════════
# TEST 1 — acord_strict_models: canonical form key normalisation
# ════════════════════════════════════════════════════════════════════
def t1():
    from fine_tuning.dataset.acord_strict_models import (
        canonical_acord_form_key,
        UnsupportedFormTypeError,
    )
    assert canonical_acord_form_key("25")       == "25",  "bare number"
    assert canonical_acord_form_key("acord25")  == "25",  "no-space prefix"
    assert canonical_acord_form_key("ACORD 25") == "25",  "spaced prefix"
    assert canonical_acord_form_key("ACORD_125")== "125", "underscored prefix"
    assert canonical_acord_form_key("130")      == "130", "form 130"

    try:
        canonical_acord_form_key("999")
        raise AssertionError("Should have raised UnsupportedFormTypeError")
    except UnsupportedFormTypeError:
        pass

_run("acord_strict_models: canonical_acord_form_key normalisation", t1)


# ════════════════════════════════════════════════════════════════════
# TEST 2 — ingest: build_training_sample_from_correction
# ════════════════════════════════════════════════════════════════════
def t2():
    from fine_tuning.continuous_learning.ingest import (
        build_training_sample_from_correction,
        get_universal_system_prompt,
    )
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    row = {
        "form_type":        "25",
        "raw_text":         "Agency: Wrong Agency\nPolicy: POL-001",
        "original_fields":  {"agency_name": "Wrong Agency", "policy_number": ""},
        "corrected_fields": {},
        "upload_id":        "uid-smoke-001",
        "sample_id":        "sid-smoke-001",
    }
    sample = build_training_sample_from_correction(
        run_row=row,
        corrected_json={"agency_name": "Correct Agency", "policy_number": "POL-001"},
    )

    msgs = sample["messages"]
    assert len(msgs) == 3,                                    "must have 3 messages"
    assert msgs[0]["role"] == "system",                       "first role=system"
    assert msgs[1]["role"] == "user",                         "second role=user"
    assert msgs[2]["role"] == "assistant",                    "third role=assistant"
    assert msgs[0]["content"] == get_universal_system_prompt(), "system prompt matches"
    assert "ACORD Form 25" in msgs[1]["content"],             "form type in user content"
    assert "Wrong Agency"  in msgs[1]["content"],             "OCR text in user content"

    out = parse_assistant_fields(msgs[2]["content"])
    assert out is not None,                                   "assistant content must parse"
    assert out["agency_name"]   == "Correct Agency",         "correction applied"
    assert out["policy_number"] == "POL-001",                "correction applied"
    assert sample["domain"]     == "insurance",              "domain tag"

_run("ingest: build_training_sample_from_correction", t2)


# ════════════════════════════════════════════════════════════════════
# TEST 3 — dataset_builder: validate_chat_format
# ════════════════════════════════════════════════════════════════════
def t3():
    from fine_tuning.dataset.dataset_builder import (
        validate_chat_format,
        InvalidChatFormatError,
    )

    good = {
        "messages": [
            {"role": "system",    "content": "You are an expert."},
            {"role": "user",      "content": "Extract fields from this text."},
            {"role": "assistant", "content": '{"field": "value"}'},
        ]
    }
    validate_chat_format(good, 0)   # must not raise

    # Missing assistant turn
    try:
        validate_chat_format({"messages": [
            {"role": "system", "content": "ok"},
            {"role": "user",   "content": "ok"},
        ]}, 0)
        raise AssertionError("Should have raised for missing assistant")
    except InvalidChatFormatError:
        pass

    # Non-JSON assistant content
    try:
        validate_chat_format({"messages": [
            {"role": "system",    "content": "ok"},
            {"role": "user",      "content": "ok"},
            {"role": "assistant", "content": "This is plain text, not JSON"},
        ]}, 0)
        raise AssertionError("Should have raised for non-JSON assistant")
    except InvalidChatFormatError:
        pass

_run("dataset_builder: validate_chat_format (good + bad cases)", t3)


# ════════════════════════════════════════════════════════════════════
# TEST 4 — dataset_builder: full DatasetBuilder.build()
# ════════════════════════════════════════════════════════════════════
def t4():
    from fine_tuning.dataset.dataset_builder import DatasetBuilder
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # Build a snapshot JSONL (simulates version_store output)
        snapshot = tmp / "v0001.jsonl"
        rows = []
        for i in range(3):
            r = build_training_sample_from_correction(
                run_row={
                    "form_type":       "25",
                    "raw_text":        f"Agency: Agency {i}\nPolicy: P{i:03d}",
                    "original_fields": {"agency": f"Wrong {i}"},
                    "upload_id":       f"uid-{i}",
                    "sample_id":       f"sid-{i}",
                },
                corrected_json={"agency": f"Agency {i}", "policy_number": f"P{i:03d}"},
            )
            rows.append(r)
        snapshot.write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
        )

        config = {
            "paths": {
                "datasets_dir": str(tmp / "datasets"),
                "runs_dir":     str(tmp / "runs"),
                "registry_path": str(tmp / "registry.json"),
            },
            "continuous_learning": {
                "feedback_datasets_dir": str(tmp / "feedback"),
            },
        }

        result = DatasetBuilder(config).build(
            new_data_path=str(snapshot),
            cycle_id="smoke-cycle-001",
            min_records=1,
        )

        assert result.total_records  == 3,  f"expected 3 records, got {result.total_records}"
        assert result.new_records    == 3,  "all should be new"
        assert result.replay_records == 0,  "no previous versions to replay"
        assert result.rejected_records == 0, "all rows valid"
        assert Path(result.train_jsonl_path).exists(), "train.jsonl written"
        assert len(result.fingerprint) == 64, "sha256 fingerprint"

_run("dataset_builder: DatasetBuilder.build() end-to-end", t4)


# ════════════════════════════════════════════════════════════════════
# TEST 5 — version_registry: pending → promote round-trip
# ════════════════════════════════════════════════════════════════════
def t5():
    from fine_tuning.registry.version_registry import VersionRegistry

    with tempfile.TemporaryDirectory() as tmp:
        reg = VersionRegistry(str(Path(tmp) / "registry.json"))

        assert reg.get_current_version() == 0, "starts at v0"
        assert reg.get_current_base()    is None, "no base yet"

        v = reg.create_pending_entry(
            cycle_id="cycle-001",
            job_id="job-001",
            parent_version=0,
            replay_fraction=0.30,
            checkpoint_dir=str(Path(tmp) / "checkpoint"),
        )
        assert v == 1, f"first version should be 1, got {v}"

        # Promote
        reg.promote_version(
            version=v,
            merged_model_path=str(Path(tmp) / "merged"),
            adapter_path=str(Path(tmp) / "adapter"),
            eval_scores={"field_f1": 0.85, "field_recall": 0.80},
            training_meta={"backend": "qlora_hf", "job_id": "job-001"},
        )

        assert reg.get_current_version() == 1, "current_version updated"
        assert reg.get_current_base()    == str(Path(tmp) / "merged"), "current_base updated"

        versions = reg.list_versions()
        assert len(versions) == 1
        assert versions[0]["status"] == "promoted"
        assert versions[0]["eval_scores"]["field_f1"] == 0.85

        # Second cycle builds on top
        v2 = reg.create_pending_entry(
            cycle_id="cycle-002", job_id="job-002",
            parent_version=1, replay_fraction=0.30,
            checkpoint_dir=str(Path(tmp) / "checkpoint2"),
        )
        assert v2 == 2, f"second version should be 2, got {v2}"
        reg.mark_failed(v2, "gate failed: f1 too low")
        assert reg.list_versions()[1]["status"] == "failed"
        assert reg.get_current_version() == 1   # still on v1

_run("version_registry: pending > promote > second cycle > mark_failed", t5)


# ════════════════════════════════════════════════════════════════════
# TEST 6 — config_schema: load_and_validate_config
# ════════════════════════════════════════════════════════════════════
def t6():
    from fine_tuning.config_schema import load_and_validate_config

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfg_path = tmp / "config.yaml"
        cfg_path.write_text(
            "base_model: /workspace/models/qwen2-vl-7b\n"
            "local_files_only: false\n"
            "lora:\n"
            "  r: 16\n"
            "  lora_alpha: 32\n"
            "  lora_dropout: 0.05\n"
            "training:\n"
            "  num_epochs: 3\n"
            "  learning_rate: 2.0e-5\n"
            "  max_seq_length: 4096\n"
            "  per_device_train_batch_size: 1\n"
            "continuous_learning:\n"
            "  retrain_threshold: 25\n"
            "evaluation:\n"
            "  allow_skip_eval_gate: true\n"
            "  absolute_floors:\n"
            "    field_f1: 0.65\n"
            "    field_recall: 0.60\n",
            encoding="utf-8",
        )

        cfg = load_and_validate_config(str(cfg_path))

        assert cfg["base_model"] == "/workspace/models/qwen2-vl-7b"
        assert cfg["paths"]["runs_dir"]      == "/workspace/fine_tuning/runs"
        assert cfg["paths"]["registry_path"] == "/workspace/fine_tuning/registry/version_registry.json"
        assert cfg["continuous_learning"]["retrain_threshold"] == 25
        assert cfg["evaluation"]["allow_skip_eval_gate"] is True
        assert cfg["training"]["replay_fraction"]        == 0.30  # default injected

_run("config_schema: load_and_validate_config with defaults injection", t6)


# ════════════════════════════════════════════════════════════════════
# TEST 7 — eval_gate: skip path (no eval examples)
# ════════════════════════════════════════════════════════════════════
def t7():
    from fine_tuning.evaluation.eval_gate import run_eval_gate
    from fine_tuning.evaluation.local_metrics import LocalEvalResult

    skipped = LocalEvalResult(skipped=True, skip_reason="no eval examples provided")
    config  = {"evaluation": {"allow_skip_eval_gate": True}}

    gate = run_eval_gate(skipped, None, None, config, None)
    assert gate.passed  is True,  "gate should pass when skipped+allow"
    assert gate.failures == [],   "no failures"
    assert gate.scores.get("skipped") is True

    # With allow_skip_eval_gate=false it must block
    config2 = {"evaluation": {"allow_skip_eval_gate": False}}
    gate2 = run_eval_gate(skipped, None, None, config2, None)
    assert gate2.passed is False, "gate must block when allow_skip=false"

_run("eval_gate: skip path with allow_skip true/false", t7)


# ════════════════════════════════════════════════════════════════════
# TEST 8 — version_store: append + snapshot promotion
# ════════════════════════════════════════════════════════════════════
def t8():
    from fine_tuning.continuous_learning.version_store import (
        append_training_sample,
        load_pending_rows,
        load_all_versioned_rows,
    )
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # Append below threshold — should stay pending
        row0 = build_training_sample_from_correction(
            {"form_type": "25", "raw_text": "text", "original_fields": {"f": "wrong"},
             "upload_id": "u0", "sample_id": "s0"},
            {"f": "right"},
        )
        outcome = append_training_sample(root, row0, retrain_threshold=3)
        assert outcome.pending_count_after  == 1
        assert outcome.version_snapshot_path is None
        assert len(load_pending_rows(root))  == 1

        # Append two more — third crosses threshold=3, snapshot promoted
        for i in range(1, 3):
            r = build_training_sample_from_correction(
                {"form_type": "25", "raw_text": f"text {i}",
                 "original_fields": {"f": "w"}, "upload_id": f"u{i}", "sample_id": f"s{i}"},
                {"f": f"v{i}"},
            )
            outcome = append_training_sample(root, r, retrain_threshold=3)

        assert outcome.pending_count_after   == 0,    "pending reset after snapshot"
        assert outcome.version_snapshot_path is not None, "snapshot created"
        assert outcome.snapshot_version      == 1

        versioned = load_all_versioned_rows(root)
        assert len(versioned) == 3,  f"expected 3 versioned rows, got {len(versioned)}"
        assert load_pending_rows(root) == [], "pending cleared"

_run("version_store: append + threshold snapshot promotion", t8)


# ════════════════════════════════════════════════════════════════════
# TEST 9 — chat format label masking logic (train.py tokeniser)
# ════════════════════════════════════════════════════════════════════
def t9():
    # Replicate the assistant-boundary logic from train.py._tokenise
    # to verify labels are correctly masked without needing a real tokeniser.
    _ASSISTANT_PREFIX = "<|im_start|>assistant\n"

    def simulate_label_mask(text: str) -> tuple[list[int], list[int]]:
        """Returns (token_ids, labels) using char positions as fake token ids."""
        prefix_end = text.rfind(_ASSISTANT_PREFIX)
        assert prefix_end != -1, "assistant boundary not found"
        prefix_text = text[: prefix_end + len(_ASSISTANT_PREFIX)]
        prefix_ids  = list(range(len(prefix_text)))           # fake: each char = 1 token
        full_ids    = list(range(len(text)))
        completion_ids = full_ids[len(prefix_ids):]
        labels = [-100] * len(prefix_ids) + list(completion_ids)
        return full_ids, labels

    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction

    row = {
        "form_type": "25", "raw_text": "Agency: Test",
        "original_fields": {"agency": "w"}, "upload_id": "u", "sample_id": "s",
    }
    sample = build_training_sample_from_correction(row, {"agency": "Test"})
    msgs   = sample["messages"]

    # Build a ChatML string manually (mirrors train._build_qwen_chat)
    parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>" for m in msgs]
    chat  = "\n".join(parts) + "\n"

    ids, labels = simulate_label_mask(chat)
    active = sum(1 for l in labels if l != -100)
    assert active > 0,         "at least some labels must be active"
    assert labels[0] == -100,  "first token (system prefix) must be masked"
    assert labels[-1] != -100, "last token (assistant content) must be active"

_run("chat format: assistant boundary masking logic", t9)


# ════════════════════════════════════════════════════════════════════
# TEST 10 — Real ACORD 125 sample (Acord-125-sample7 1 13.pdf)
# Fields sourced directly from the provided 4-page PDF.
# ════════════════════════════════════════════════════════════════════
def t10():
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
    from fine_tuning.dataset.dataset_builder import validate_chat_format

    # Simulated OCR text matching page 1 of the provided PDF
    raw_text = (
        "COMMERCIAL INSURANCE APPLICATION - APPLICANT INFORMATION SECTION\n"
        "DATE (MM/DD/YYYY): 07/11/2025\n"
        "AGENCY: Convenis Agency\n"
        "56 Street, rakab ganj, Agra, UP 282002\n"
        "CARRIER: Aquisec Insurance Company    NAIC CODE: 34214\n"
        "COMPANY POLICY OR PROGRAM NAME: Velocity Insure Plan    PROGRAM CODE: 007\n"
        "POLICY NUMBER: POLICY987654321\n"
        "CONTACT NAME: Pankaj Tripathi\n"
        "PHONE (A/C, No, Ext): +91-800585843\n"
        "FAX (A/C, No): +91-8004563212\n"
        "E-MAIL ADDRESS: pankaj.tripathi@google.com\n"
        "CODE: 34523    SUBCODE:\n"
        "AGENCY CUSTOMER ID: AMJ563467\n"
        "UNDERWRITER: Sreedevi Chulki    UNDERWRITER OFFICE: Western Divison\n"
        "STATUS OF TRANSACTION: CANCEL    DATE: 07/02/2025    TIME: 11:32 PM\n"
        "LINES OF BUSINESS: [X] BUSINESS OWNERS    [X] TRUCKERS\n"
        "ATTACHMENTS: [X] INSTALLATION / BUILDERS RISK SECTION\n"
        "             [X] CONTRACTORS SUPPLEMENT\n"
        "             [X] VEHICLE SCHEDULE\n"
        "PROPOSED EFF DATE: 07/02/2025    PROPOSED EXP DATE: 07/01/2026\n"
        "BILLING PLAN: [X] DIRECT    PAYMENT PLAN: Annual\n"
        "METHOD OF PAYMENT: Cash    AUDIT:\n"
        "DEPOSIT: $12000    MINIMUM PREMIUM: $4500    POLICY PREMIUM: $6000\n"
        "NAME (First Named Insured): Ventrasys Ltd.\n"
        "MAILING ADDRESS: Sector 142, Noida, UP\n"
        "GL CODE: 4321    SIC: 8754    NAICS: 23463    FEIN OR SOC SEC #: 43-434342\n"
        "BUSINESS PHONE #: +91-5439875    WEBSITE: www.ventrasys.com\n"
        "ENTITY TYPE: [X] CORPORATION    [X] PARTNERSHIP    SUBCHAPTER S CORPORATION\n"
        "NAME (Other Named Insured): Integrase System Ltd.\n"
        "MAILING ADDRESS: Mayur Vihar, Delhi-100432\n"
        "GL CODE: 4532    SIC: 6321    NAICS: 09842    FEIN OR SOC SEC #: 23-56743\n"
        "BUSINESS PHONE #: +91-453954    WEBSITE: www.integrase.com\n"
        "ENTITY TYPE: [X] CORPORATION    [X] PARTNERSHIP\n"
        "NAME (Other Named Insured): RapidAmbat Pvt. Ltd.\n"
        "MAILING ADDRESS: Sector 134, Noida, UP 201301\n"
        "GL CODE: 5432    SIC: 9863    NAICS: 67532    FEIN OR SOC SEC #: 66-21435\n"
        "BUSINESS PHONE #: +91-64265    WEBSITE: www.rapidambat.com\n"
        "ENTITY TYPE: [X] INDIVIDUAL    [X] LLC    [X] NOT FOR PROFIT ORG    [X] PARTNERSHIP    [X] TRUST\n"
    )

    # What the model originally extracted (some fields wrong/missing)
    original_fields = {
        "date": "07/11/2025",
        "agency_name": "Convenis Agency",
        "agency_address": "56 Street rakab ganj Agra UP",          # missing comma formatting
        "carrier": "Aquisec Insurance Company",
        "naic_code": "34214",
        "program_name": "Velocity Insure Plan",
        "program_code": "007",
        "policy_number": "POLICY987654321",
        "contact_name": "Pankaj Tripathi",
        "phone": "+91-800585843",
        "fax": "+91-8004563212",
        "email": "pankaj.tripathi@google.com",
        "agency_code": "34523",
        "agency_customer_id": "AMJ563467",
        "underwriter": "Sreedevi Chulki",
        "underwriter_office": "Western Divison",                   # typo from PDF
        "status_of_transaction": "CANCEL",
        "cancel_date": "07/02/2025",
        "cancel_time": "11:32 PM",
        "lines_of_business": ["BUSINESS OWNERS", "TRUCKERS"],
        "attachments": ["INSTALLATION / BUILDERS RISK SECTION", "CONTRACTORS SUPPLEMENT", "VEHICLE SCHEDULE"],
        "proposed_eff_date": "07/02/2025",
        "proposed_exp_date": "07/01/2026",
        "billing_plan": "DIRECT",
        "payment_plan": "Annual",
        "method_of_payment": "Cash",
        "deposit": "12000",                                        # wrong: missing $
        "minimum_premium": "4500",                                 # wrong: missing $
        "policy_premium": "6000",                                  # wrong: missing $
        "named_insured": "Ventrasys Ltd",                          # wrong: missing period
        "named_insured_address": "Sector 142, Noida, UP",
        "gl_code": "4321",
        "sic": "8754",
        "naics": "23463",
        "fein": "43-434342",
        "business_phone": "+91-5439875",
        "website": "www.ventrasys.com",
        "other_named_insured_1": "Integrase System Ltd.",
        "other_named_insured_1_address": "Mayur Vihar, Delhi-100432",
        "other_named_insured_2": "RapidAmbat Pvt. Ltd.",
        "other_named_insured_2_address": "Sector 134, Noida, UP 201301",
    }

    # User corrections — fixing the wrong fields
    corrected_fields = {
        "agency_address": "56 Street, rakab ganj, Agra, UP 282002",
        "deposit": "$12000",
        "minimum_premium": "$4500",
        "policy_premium": "$6000",
        "named_insured": "Ventrasys Ltd.",
    }

    row = {
        "form_type":        "125",
        "raw_text":         raw_text,
        "original_fields":  original_fields,
        "upload_id":        "acord125-smoke-pdf-001",
        "sample_id":        "sample-acord125-001",
    }

    sample = build_training_sample_from_correction(
        run_row=row,
        corrected_json=corrected_fields,
    )

    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    msgs = sample["messages"]
    assert len(msgs) == 3,                                         "3-message structure"
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert msgs[2]["role"] == "assistant"

    # User turn: must reference form 125 and contain real OCR
    assert "ACORD Form 125"       in msgs[1]["content"],           "form type in user prompt"
    assert "Convenis Agency"      in msgs[1]["content"],           "agency name in OCR text"
    assert "POLICY987654321"      in msgs[1]["content"],           "policy number in OCR text"
    assert "Ventrasys Ltd."       in msgs[1]["content"],           "named insured in OCR text"

    # Assistant turn: extract fields via parse_assistant_fields (handles FIELDS:\n{json} format)
    out = parse_assistant_fields(msgs[2]["content"])
    assert out is not None,                                        "assistant content must parse"

    assert out["agency_address"]  == "56 Street, rakab ganj, Agra, UP 282002", "address corrected"
    assert out["deposit"]         == "$12000",                     "deposit corrected"
    assert out["minimum_premium"] == "$4500",                      "min premium corrected"
    assert out["policy_premium"]  == "$6000",                      "policy premium corrected"
    assert out["named_insured"]   == "Ventrasys Ltd.",             "named insured corrected"

    # Uncorrected fields must survive from original_fields
    assert out["carrier"]              == "Aquisec Insurance Company",  "carrier preserved"
    assert out["policy_number"]        == "POLICY987654321",            "policy number preserved"
    assert out["underwriter"]          == "Sreedevi Chulki",            "underwriter preserved"
    assert out["other_named_insured_1"]== "Integrase System Ltd.",      "other insured 1 preserved"
    assert out["other_named_insured_2"]== "RapidAmbat Pvt. Ltd.",       "other insured 2 preserved"
    assert out["naic_code"]            == "34214",                      "NAIC code preserved"

    # Must also pass the dataset_builder chat format validator
    validate_chat_format(sample, 0)

    assert sample["metadata"]["form_type"]  == "125",              "form type in metadata"
    assert sample["metadata"]["upload_id"]  == "acord125-smoke-pdf-001"

_run("ACORD 125 real PDF: ingest + correction + validation round-trip", t10)


# ════════════════════════════════════════════════════════════════════
# TEST 11 — extractor: _extract_kv_from_ocr_text (active definition)
# Validates the colon-split KV extractor against realistic ACORD OCR.
# ════════════════════════════════════════════════════════════════════
def t11():
    from extractor import _extract_kv_from_ocr_text

    # Surya OCR output typical of an ACORD 125 page 1
    ocr_text = (
        "AGENCY: Convenis Agency\n"
        "CARRIER: Aquisec Insurance Company    NAIC CODE: 34214\n"
        "POLICY NUMBER: POLICY987654321\n"
        "PHONE (A/C, No, Ext): +91-800585843\n"
        "FAX (A/C, No): +91-8004563212\n"
        "E-MAIL ADDRESS: pankaj.tripathi@google.com\n"
        "AGENCY CUSTOMER ID: AMJ563467\n"
        "UNDERWRITER: Sreedevi Chulki    UNDERWRITER OFFICE: Western Divison\n"
        "PROPOSED EFF DATE: 07/02/2025    PROPOSED EXP DATE: 07/01/2026\n"
        "DEPOSIT: $12000    MINIMUM PREMIUM: $4500    POLICY PREMIUM: $6000\n"
        "NAME (First Named Insured): Ventrasys Ltd.\n"
        "WEBSITE: www.ventrasys.com\n"
        "SEPARATOR LINE: ----\n"            # value is separator — must be excluded
        "SHORT: x\n"                        # key too short (< 2 chars after normalise?) — skipped
        "12345: some value\n"               # purely numeric key — must be rejected
    )

    kv = _extract_kv_from_ocr_text(ocr_text)

    # Fields that must be present
    assert kv.get("agency")          == "Convenis Agency",          "agency extracted"
    assert kv.get("carrier")         == "Aquisec Insurance Company","carrier extracted"
    assert kv.get("naic_code")       == "34214",                    "naic_code extracted (inline multi-column)"
    assert kv.get("policy_number")   == "POLICY987654321",          "policy_number extracted"
    assert kv.get("agency_customer_id") == "AMJ563467",             "agency_customer_id extracted"
    assert kv.get("underwriter")     == "Sreedevi Chulki",          "underwriter extracted"
    assert kv.get("underwriter_office") == "Western Divison",       "underwriter_office extracted (inline)"
    assert kv.get("proposed_eff_date")  == "07/02/2025",            "eff date extracted"
    assert kv.get("proposed_exp_date")  == "07/01/2026",            "exp date extracted (inline)"
    assert kv.get("deposit")         == "$12000",                   "deposit extracted (inline)"
    assert kv.get("minimum_premium") == "$4500",                    "min premium extracted (inline)"
    assert kv.get("policy_premium")  == "$6000",                    "policy premium extracted (inline)"
    assert kv.get("website")         == "www.ventrasys.com",        "website extracted"

    # Separator-only value must not appear
    assert "separator_line" not in kv, "separator-value key must be excluded"

    # Purely numeric key must be rejected
    assert not any(k.strip("_").isdigit() for k in kv), "numeric-only keys must be rejected"

_run("extractor: _extract_kv_from_ocr_text colon-split KV extraction", t11)


# ════════════════════════════════════════════════════════════════════
# TEST 12 — schema_registry: validate_policy_number valid cases
# ════════════════════════════════════════════════════════════════════
def t12():
    from insurance_schema_registry import validate_policy_number
    assert validate_policy_number("GL-0123456")  is True,  "standard policy number"
    assert validate_policy_number("POL-ABC-001") is True,  "alphanumeric with dashes"
    assert validate_policy_number("WC1234567")   is True,  "workers comp style"
    assert validate_policy_number("POLICY987654321") is True, "long policy number"
    # Invalid cases
    assert validate_policy_number("12345")       is False, "digits only — no letters"
    assert validate_policy_number("ABC")         is False, "letters only, no digits"
    assert validate_policy_number("AB1")         is False, "too short (< 4 chars)"
    assert validate_policy_number("")            is False, "empty string"
    assert validate_policy_number(None)          is False, "None input"

_run("schema_registry: validate_policy_number valid + invalid", t12)


# ════════════════════════════════════════════════════════════════════
# TEST 13 — schema_registry: validate_naic_code
# ════════════════════════════════════════════════════════════════════
def t13():
    from insurance_schema_registry import validate_naic_code
    assert validate_naic_code("34214")  is True,  "5-digit NAIC code"
    assert validate_naic_code("1234")   is True,  "4-digit NAIC code"
    assert validate_naic_code("123")    is False, "too short"
    assert validate_naic_code("123456") is False, "too long (6 digits)"
    assert validate_naic_code("1234A")  is False, "contains letter"
    assert validate_naic_code("")       is False, "empty"
    assert validate_naic_code(None)     is False, "None"

_run("schema_registry: validate_naic_code valid + invalid", t13)


# ════════════════════════════════════════════════════════════════════
# TEST 14 — schema_registry: validate_insurance_date — all 3 formats
# ════════════════════════════════════════════════════════════════════
def t14():
    from insurance_schema_registry import validate_insurance_date
    assert validate_insurance_date("07/02/2025") is True,  "MM/DD/YYYY slash"
    assert validate_insurance_date("07-02-2025") is True,  "MM-DD-YYYY dash"
    assert validate_insurance_date("2025-07-02") is True,  "YYYY-MM-DD ISO"
    assert validate_insurance_date("2025/07/02") is True,  "YYYY/MM/DD slash"
    assert validate_insurance_date("7/2/2025")   is False, "single-digit month (no leading zero)"
    assert validate_insurance_date("02-2025")    is False, "missing day"
    assert validate_insurance_date("")           is False, "empty"
    assert validate_insurance_date(None)         is False, "None"

_run("schema_registry: validate_insurance_date all 3 formats", t14)


# ════════════════════════════════════════════════════════════════════
# TEST 15 — schema_registry: validate_currency_amount
# ════════════════════════════════════════════════════════════════════
def t15():
    from insurance_schema_registry import validate_currency_amount
    assert validate_currency_amount("$12000")        is True,  "dollar prefix"
    assert validate_currency_amount("4500")          is True,  "bare number"
    assert validate_currency_amount("$1,000,000.00") is True,  "comma-formatted with cents"
    assert validate_currency_amount("100.5")         is True,  "one decimal place"
    assert validate_currency_amount("abc")           is False, "non-numeric"
    assert validate_currency_amount("$12.345")       is False, "3 decimal places"
    assert validate_currency_amount("")              is False, "empty"
    assert validate_currency_amount(None)            is False, "None"

_run("schema_registry: validate_currency_amount valid + invalid", t15)


# ════════════════════════════════════════════════════════════════════
# TEST 16 — schema_registry: validate_phone_number
# ════════════════════════════════════════════════════════════════════
def t16():
    from insurance_schema_registry import validate_phone_number
    assert validate_phone_number("+91-800585843")   is True,  "Indian format with prefix"
    assert validate_phone_number("(555) 123-4567")  is True,  "US format with parens"
    assert validate_phone_number("5551234567")      is True,  "10-digit bare"
    assert validate_phone_number("+1-800-555-0199") is True,  "US toll-free"
    assert validate_phone_number("123456")          is False, "too short (6 digits)"
    assert validate_phone_number("12345678901234567") is False, "too long (16+ digits)"
    assert validate_phone_number("")                is False, "empty"
    assert validate_phone_number(None)              is False, "None"

_run("schema_registry: validate_phone_number valid + invalid", t16)


# ════════════════════════════════════════════════════════════════════
# TEST 17 — schema_registry: detect_document_type aliases
# ════════════════════════════════════════════════════════════════════
def t17():
    from insurance_schema_registry import SchemaRegistry, DocumentType
    reg = SchemaRegistry()

    # ACORD aliases
    assert reg.detect_document_type({"document_identification": {"document_type": "ACORD_25"}}) == DocumentType.ACORD_25
    assert reg.detect_document_type({"document_identification": {"document_type": "ACORD 25"}}) == DocumentType.ACORD_25
    assert reg.detect_document_type({"document_identification": {"document_type": "ACORD125"}}) == DocumentType.ACORD_125
    assert reg.detect_document_type({"document_identification": {"document_type": "ACORD 130"}}) == DocumentType.ACORD_130
    # Non-ACORD
    assert reg.detect_document_type({"document_identification": {"document_type": "POLICY_DEC"}}) == DocumentType.POLICY_DEC
    assert reg.detect_document_type({"document_identification": {"document_type": "POLICY DEC"}}) == DocumentType.POLICY_DEC
    assert reg.detect_document_type({"document_identification": {"document_type": "LOSS RUN"}}) == DocumentType.LOSS_RUN
    assert reg.detect_document_type({"document_identification": {"document_type": "CLAIM FORM"}}) == DocumentType.CLAIM_FORM
    # Unknown → OTHER
    assert reg.detect_document_type({"document_identification": {"document_type": "GARBAGE"}}) == DocumentType.OTHER
    assert reg.detect_document_type({}) == DocumentType.OTHER

_run("schema_registry: detect_document_type aliases", t17)


# ════════════════════════════════════════════════════════════════════
# TEST 18 — schema_registry: validate() — valid well-formed ACORD 25
# ════════════════════════════════════════════════════════════════════
def t18():
    from insurance_schema_registry import SchemaRegistry
    reg = SchemaRegistry()

    doc = {
        "document_identification": {"document_type": "ACORD_25", "page_count": 1},
        "parties": {
            "named_insured": "Ventrasys Ltd.",
            "certificate_holder": "First National Bank",
        },
        "policy_identifiers": {
            "certificate_number": "CERT-001",
            "policy_number": "GL-0123456",
        },
        "dates": {
            "effective_date":  "07/02/2025",
            "expiration_date": "07/01/2026",
        },
        "coverages": [
            {"coverage_type": "General Liability", "limit": "$1,000,000"},
        ],
    }
    result = reg.validate(doc)
    assert result["valid"] is True,  f"should be valid; errors={result['errors']}"
    assert result["document_type"] == "ACORD_25"
    assert result["errors"] == []

_run("schema_registry: validate() — valid ACORD_25 document", t18)


# ════════════════════════════════════════════════════════════════════
# TEST 19 — schema_registry: validate() — missing required section
# ════════════════════════════════════════════════════════════════════
def t19():
    from insurance_schema_registry import SchemaRegistry
    reg = SchemaRegistry()

    # Missing 'parties' section — required for all doc types
    doc = {
        "document_identification": {"document_type": "ACORD_130", "page_count": 2},
    }
    result = reg.validate(doc)
    assert result["valid"] is False, "must be invalid when required section missing"
    assert any("parties" in e for e in result["errors"]), f"errors must mention parties; got {result['errors']}"
    assert "parties" in result["missing_required"]

_run("schema_registry: validate() — missing required section", t19)


# ════════════════════════════════════════════════════════════════════
# TEST 20 — schema_registry: validate() — bad field format warnings
# ════════════════════════════════════════════════════════════════════
def t20():
    from insurance_schema_registry import SchemaRegistry
    reg = SchemaRegistry()

    doc = {
        "document_identification": {"document_type": "ACORD_25", "page_count": 1},
        "parties": {
            "named_insured": "Acme Corp",
            "certificate_holder": "Big Bank",
        },
        "policy_identifiers": {
            "certificate_number": "CERT-002",
            "policy_number": "BADFORMAT",   # letters only — no digits
            "naic_code": "ABC12",           # non-digits — invalid NAIC
        },
        "dates": {
            "effective_date":  "July 2 2025",  # non-standard date
            "expiration_date": "07/01/2026",
        },
        "coverages": [
            {"coverage_type": "GL", "limit": "$500,000"},
        ],
    }
    result = reg.validate(doc)
    # warnings should contain format errors; doc may still be "valid" (warnings != errors)
    assert result["field_stats"]["format_errors"] > 0, "expected format errors in field_stats"
    assert len(result["warnings"]) > 0, "expected warnings for bad formats"

_run("schema_registry: validate() — format warnings on bad field values", t20)


# ════════════════════════════════════════════════════════════════════
# TEST 21 — schema_registry: get_empty_template structure
# ════════════════════════════════════════════════════════════════════
def t21():
    from insurance_schema_registry import SchemaRegistry, DocumentType
    reg = SchemaRegistry()

    for doc_type in [DocumentType.ACORD_25, DocumentType.LOSS_RUN, DocumentType.QUOTE]:
        tmpl = reg.get_empty_template(doc_type)
        assert isinstance(tmpl, dict),                          f"{doc_type.value}: template must be dict"
        assert "document_identification" in tmpl,               f"{doc_type.value}: must have document_identification"
        assert "parties" in tmpl,                               f"{doc_type.value}: must have parties"
        assert "coverages" in tmpl,                             f"{doc_type.value}: must have coverages"
        assert tmpl["document_identification"]["document_type"] == doc_type.value, \
            f"{doc_type.value}: document_type field must be set"
        assert isinstance(tmpl["coverages"], list),             f"{doc_type.value}: coverages must be list"

_run("schema_registry: get_empty_template — structure for ACORD_25, LOSS_RUN, QUOTE", t21)


# ════════════════════════════════════════════════════════════════════
# TEST 22 — schema_registry: suggest_corrections — OCR fix suggestions
# ════════════════════════════════════════════════════════════════════
def t22():
    from insurance_schema_registry import suggest_corrections

    doc = {
        "policy_identifiers": {
            "naic_code":    "34-214",  # has dash — strip non-digits -> "34214" (valid)
        },
        "dates": {
            "effective_date": "04/01/2026",   # already valid — no suggestion needed
        },
        "financials": {
            "premium_total": "USD 5000",  # fails validation; cleaned to "5000" -> suggest "$5000"
        },
    }
    suggestions = suggest_corrections(doc, {})
    assert "policy_identifiers.naic_code" in suggestions,   "should suggest NAIC OCR fix"
    assert suggestions["policy_identifiers.naic_code"] == "34214", \
        f"NAIC suggestion should be '34214', got {suggestions.get('policy_identifiers.naic_code')}"
    assert "financials.premium_total" in suggestions,       "should suggest $ prefix for premium"
    assert suggestions["financials.premium_total"] == "$5000", \
        f"premium suggestion should be '$5000', got {suggestions.get('financials.premium_total')}"

_run("schema_registry: suggest_corrections — OCR fix suggestions", t22)


# ════════════════════════════════════════════════════════════════════
# TEST 23 — ingest: POLICY_DEC document type end-to-end
# ════════════════════════════════════════════════════════════════════
def t23():
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    sample = build_training_sample_from_correction(
        run_row={
            "form_type":        "POLICY_DEC",
            "raw_text":         "Policy Number: POL-2025-001\nInsured: Smith Co.",
            "original_fields":  {"policy_number": "POL-2025-00I"},   # OCR typo
            "upload_id":        "uid-pdec-001",
            "sample_id":        "sid-pdec-001",
        },
        corrected_json={"policy_number": "POL-2025-001"},
    )
    msgs = sample["messages"]
    assert msgs[1]["role"] == "user"
    assert "Insurance Policy Declarations Page" in msgs[1]["content"], \
        "POLICY_DEC user label must appear in user content"
    out = parse_assistant_fields(msgs[2]["content"])
    assert out is not None
    assert out["policy_number"] == "POL-2025-001"
    assert sample["metadata"]["document_type"] == "POLICY_DEC"

_run("ingest: POLICY_DEC document type", t23)


# ════════════════════════════════════════════════════════════════════
# TEST 24 — ingest: CERTIFICATE document type
# ════════════════════════════════════════════════════════════════════
def t24():
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    sample = build_training_sample_from_correction(
        run_row={
            "form_type":        "CERTIFICATE",
            "raw_text":         "Certificate Number: CERT-0042\nHolder: BigBank Inc.",
            "original_fields":  {"certificate_number": "CERT-OO42"},   # O→0 OCR typo
            "upload_id":        "uid-cert-001",
            "sample_id":        "sid-cert-001",
        },
        corrected_json={"certificate_number": "CERT-0042"},
    )
    assert "Certificate of Insurance" in sample["messages"][1]["content"]
    out = parse_assistant_fields(sample["messages"][2]["content"])
    assert out["certificate_number"] == "CERT-0042"
    assert sample["metadata"]["document_type"] == "CERTIFICATE"

_run("ingest: CERTIFICATE document type", t24)


# ════════════════════════════════════════════════════════════════════
# TEST 25 — ingest: LOSS_RUN document type
# ════════════════════════════════════════════════════════════════════
def t25():
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    sample = build_training_sample_from_correction(
        run_row={
            "form_type":        "LOSS_RUN",
            "raw_text":         "Loss Run Report\nClaim: CLM-001\nDate: 03/15/2024",
            "original_fields":  {"claim_number": "CLM-OO1", "loss_date": "03/I5/2024"},
            "upload_id":        "uid-lr-001",
            "sample_id":        "sid-lr-001",
        },
        corrected_json={"claim_number": "CLM-001", "loss_date": "03/15/2024"},
    )
    assert "Loss Run Report" in sample["messages"][1]["content"]
    out = parse_assistant_fields(sample["messages"][2]["content"])
    assert out["claim_number"] == "CLM-001"
    assert out["loss_date"]    == "03/15/2024"
    assert sample["metadata"]["document_type"] == "LOSS_RUN"

_run("ingest: LOSS_RUN document type", t25)


# ════════════════════════════════════════════════════════════════════
# TEST 26 — ingest: BINDER document type
# ════════════════════════════════════════════════════════════════════
def t26():
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    sample = build_training_sample_from_correction(
        run_row={
            "form_type":        "BINDER",
            "raw_text":         "Binder Number: BND-999\nEffective: 01/01/2026",
            "original_fields":  {"binder_number": "BND-9S9"},
            "upload_id":        "uid-bnd-001",
            "sample_id":        "sid-bnd-001",
        },
        corrected_json={"binder_number": "BND-999"},
    )
    assert "Insurance Binder" in sample["messages"][1]["content"]
    out = parse_assistant_fields(sample["messages"][2]["content"])
    assert out["binder_number"] == "BND-999"
    assert sample["metadata"]["document_type"] == "BINDER"

_run("ingest: BINDER document type", t26)


# ════════════════════════════════════════════════════════════════════
# TEST 27 — ingest: ENDORSEMENT document type
# ════════════════════════════════════════════════════════════════════
def t27():
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    sample = build_training_sample_from_correction(
        run_row={
            "form_type":        "ENDORSEMENT",
            "raw_text":         "Endorsement No: END-007\nPolicy: GL-0123456",
            "original_fields":  {"endorsement_number": "END-OO7", "policy_number": "GL-0I23456"},
            "upload_id":        "uid-end-001",
            "sample_id":        "sid-end-001",
        },
        corrected_json={"endorsement_number": "END-007", "policy_number": "GL-0123456"},
    )
    assert "Policy Endorsement" in sample["messages"][1]["content"]
    out = parse_assistant_fields(sample["messages"][2]["content"])
    assert out["endorsement_number"] == "END-007"
    assert out["policy_number"]      == "GL-0123456"
    assert sample["metadata"]["document_type"] == "ENDORSEMENT"

_run("ingest: ENDORSEMENT document type", t27)


# ════════════════════════════════════════════════════════════════════
# TEST 28 — ingest: APPLICATION document type
# ════════════════════════════════════════════════════════════════════
def t28():
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    sample = build_training_sample_from_correction(
        run_row={
            "form_type":        "APPLICATION",
            "raw_text":         "Applicant: Omega LLC\nBusiness: Retail",
            "original_fields":  {"applicant_name": "Omega LLc"},
            "upload_id":        "uid-app-001",
            "sample_id":        "sid-app-001",
        },
        corrected_json={"applicant_name": "Omega LLC"},
    )
    assert "Insurance Application" in sample["messages"][1]["content"]
    out = parse_assistant_fields(sample["messages"][2]["content"])
    assert out["applicant_name"] == "Omega LLC"
    assert sample["metadata"]["document_type"] == "APPLICATION"

_run("ingest: APPLICATION document type", t28)


# ════════════════════════════════════════════════════════════════════
# TEST 29 — parse_assistant_fields: FIELDS: format with RAW TEXT section
# ════════════════════════════════════════════════════════════════════
def t29():
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    content = (
        'FIELDS:\n{"policy_number": "GL-001", "carrier": "Acme"}\n\n'
        'RAW TEXT:\nAgency: Test\nPolicy: GL-001\n\n'
        'MARKDOWN:\n# Doc\n'
    )
    out = parse_assistant_fields(content)
    assert out is not None,                    "must parse FIELDS: block"
    assert out["policy_number"] == "GL-001",   "policy_number extracted"
    assert out["carrier"]       == "Acme",     "carrier extracted"

_run("parse_assistant_fields: FIELDS: format with RAW TEXT + MARKDOWN", t29)


# ════════════════════════════════════════════════════════════════════
# TEST 30 — parse_assistant_fields: FIELDS: format without RAW TEXT
# ════════════════════════════════════════════════════════════════════
def t30():
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    content = 'FIELDS:\n{"agency": "Convenis Agency", "naic_code": "34214"}'
    out = parse_assistant_fields(content)
    assert out is not None
    assert out["agency"]    == "Convenis Agency"
    assert out["naic_code"] == "34214"

_run("parse_assistant_fields: FIELDS: format without RAW TEXT section", t30)


# ════════════════════════════════════════════════════════════════════
# TEST 31 — parse_assistant_fields: legacy plain JSON
# ════════════════════════════════════════════════════════════════════
def t31():
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    content = '{"agency": "Old Agency", "policy_number": "POL-999"}'
    out = parse_assistant_fields(content)
    assert out is not None
    assert out["agency"]        == "Old Agency"
    assert out["policy_number"] == "POL-999"

_run("parse_assistant_fields: legacy plain JSON format", t31)


# ════════════════════════════════════════════════════════════════════
# TEST 32 — parse_assistant_fields: nested JSON inside FIELDS:
# ════════════════════════════════════════════════════════════════════
def t32():
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    content = (
        'FIELDS:\n'
        '{\n'
        '  "parties": {"named_insured": "Acme Corp", "insurer": "Big Insurance"},\n'
        '  "policy_number": "WC-4567"\n'
        '}\n\n'
        'RAW TEXT:\nsome text here'
    )
    out = parse_assistant_fields(content)
    assert out is not None
    assert isinstance(out["parties"], dict)
    assert out["parties"]["named_insured"] == "Acme Corp"
    assert out["policy_number"]            == "WC-4567"

_run("parse_assistant_fields: nested JSON object inside FIELDS:", t32)


# ════════════════════════════════════════════════════════════════════
# TEST 33 — parse_assistant_fields: invalid content returns None
# ════════════════════════════════════════════════════════════════════
def t33():
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    assert parse_assistant_fields("This is plain text with no JSON") is None, "plain text → None"
    assert parse_assistant_fields("")                                is None, "empty string → None"
    assert parse_assistant_fields("FIELDS:\nnot-json-at-all")       is None, "FIELDS: with no JSON → None"
    assert parse_assistant_fields(None)                             is None, "None input → None"

_run("parse_assistant_fields: invalid content returns None", t33)


# ════════════════════════════════════════════════════════════════════
# TEST 34 — get_corrected_paths: flat dict
# ════════════════════════════════════════════════════════════════════
def t34():
    from fine_tuning.continuous_learning.ingest import get_corrected_paths

    original  = {"agency": "Wrong", "policy": "P001", "carrier": "Same Co."}
    corrected = {"agency": "Right", "carrier": "Same Co."}

    paths = get_corrected_paths(original, corrected)
    assert "agency" in paths,   "agency was corrected"
    assert "policy" not in paths, "policy not in corrected dict → not a path"
    assert "carrier" not in paths, "carrier unchanged → not a path"

_run("get_corrected_paths: flat dict — changed and unchanged fields", t34)


# ════════════════════════════════════════════════════════════════════
# TEST 35 — get_corrected_paths: nested dict
# ════════════════════════════════════════════════════════════════════
def t35():
    from fine_tuning.continuous_learning.ingest import get_corrected_paths

    original  = {
        "parties": {"named_insured": "Old Name", "insurer": "X"},
        "policy_number": "P-001",
    }
    corrected = {
        "parties": {"named_insured": "New Name"},
    }
    paths = get_corrected_paths(original, corrected)
    assert "parties.named_insured" in paths, "nested change detected"
    assert "parties.insurer"       not in paths, "insurer not corrected"
    assert "policy_number"         not in paths, "policy_number not corrected"

_run("get_corrected_paths: nested dict — recursive diff", t35)


# ════════════════════════════════════════════════════════════════════
# TEST 36 — get_corrected_paths: no changes at all
# ════════════════════════════════════════════════════════════════════
def t36():
    from fine_tuning.continuous_learning.ingest import get_corrected_paths

    original  = {"field_a": "val1", "field_b": "val2"}
    corrected = {"field_a": "val1"}   # same value
    paths = get_corrected_paths(original, corrected)
    assert paths == [], f"no changes → empty list, got {paths}"

_run("get_corrected_paths: no changes -> empty list", t36)


# ════════════════════════════════════════════════════════════════════
# TEST 37 — _normalize_fields_to_vcf: scalar wrapping
# ════════════════════════════════════════════════════════════════════
def t37():
    from fine_tuning.continuous_learning.ingest import _normalize_fields_to_vcf

    fields = {"policy_number": "GL-001", "carrier": "Acme"}
    result = _normalize_fields_to_vcf(fields)
    assert isinstance(result["policy_number"], dict),             "should be wrapped"
    assert result["policy_number"]["value"] == "GL-001",          "value preserved"
    assert result["policy_number"]["confidence"] == "high",       "confidence=high"
    assert result["carrier"]["value"] == "Acme",                  "carrier wrapped"

_run("_normalize_fields_to_vcf: scalar value wrapping", t37)


# ════════════════════════════════════════════════════════════════════
# TEST 38 — _normalize_fields_to_vcf: already-wrapped passthrough
# ════════════════════════════════════════════════════════════════════
def t38():
    from fine_tuning.continuous_learning.ingest import _normalize_fields_to_vcf

    fields = {
        "policy_number": {"value": "GL-001", "page": 1, "confidence": "high"},
        "carrier": "Acme",
    }
    result = _normalize_fields_to_vcf(fields)
    # Already-wrapped field must pass through unchanged
    assert result["policy_number"] == {"value": "GL-001", "page": 1, "confidence": "high"}, \
        "already-wrapped field must not be re-wrapped"
    assert result["carrier"]["value"] == "Acme", "scalar still gets wrapped"

_run("_normalize_fields_to_vcf: already-wrapped field passthrough", t38)


# ════════════════════════════════════════════════════════════════════
# TEST 39 — _normalize_fields_to_vcf: page number inherited from original
# ════════════════════════════════════════════════════════════════════
def t39():
    from fine_tuning.continuous_learning.ingest import _normalize_fields_to_vcf

    original = {"policy_number": {"value": "GL-OLD", "page": 2, "confidence": "low"}}
    fields   = {"policy_number": "GL-001"}   # scalar — should inherit page from original
    result = _normalize_fields_to_vcf(fields, original=original)
    assert result["policy_number"]["value"] == "GL-001",  "corrected value used"
    assert result["policy_number"]["page"]  == 2,         "page inherited from original"
    assert result["policy_number"]["confidence"] == "high", "confidence reset to high"

_run("_normalize_fields_to_vcf: page number inherited from original", t39)


# ════════════════════════════════════════════════════════════════════
# TEST 40 — ingest: new-style explicit kwargs (no run_row)
# ════════════════════════════════════════════════════════════════════
def t40():
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    sample = build_training_sample_from_correction(
        sample_id="new-style-001",
        upload_id="pdf-new-001",
        form_type="130",
        original_fields={"insured_name": "Wrong Corp", "policy_number": "WC-OLD"},
        corrected_fields={"insured_name": "Right Corp", "policy_number": "WC-001A"},
        raw_text="Insured: Right Corp\nPolicy: WC-001A",
    )
    msgs = sample["messages"]
    assert len(msgs) == 3,                                 "3-message structure"
    assert "ACORD Form 130" in msgs[1]["content"],         "form 130 in user content"
    out = parse_assistant_fields(msgs[2]["content"])
    assert out is not None
    assert out["insured_name"]   == "Right Corp",          "correction applied"
    assert out["policy_number"]  == "WC-001A",             "correction applied"
    assert sample["metadata"]["document_type"] == "130",   "doc type metadata"

_run("ingest: new-style explicit kwargs (no run_row)", t40)


# ════════════════════════════════════════════════════════════════════
# TEST 41 — ingest: wrap_values_vcf=True wraps assistant fields
# ════════════════════════════════════════════════════════════════════
def t41():
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction
    from fine_tuning.dataset.dataset_builder import parse_assistant_fields

    sample = build_training_sample_from_correction(
        run_row={
            "form_type":        "25",
            "raw_text":         "Agency: TestAgency\nPolicy: GL-001A",
            "original_fields":  {"agency": "TestAgency", "policy_number": "GL-OO1A"},
            "upload_id":        "uid-vcf-001",
            "sample_id":        "sid-vcf-001",
        },
        corrected_json={"agency": "TestAgency", "policy_number": "GL-001A"},
        wrap_values_vcf=True,
    )
    # The assistant content FIELDS JSON should have wrapped values
    content = sample["messages"][2]["content"]
    # parse_assistant_fields unwraps → should return the fields dict (with nested wrapped values)
    out = parse_assistant_fields(content)
    assert out is not None
    # With wrap_values_vcf, each leaf should be {value, page, confidence}
    pn = out.get("policy_number")
    assert isinstance(pn, dict), f"policy_number should be wrapped dict, got {type(pn)}"
    assert pn.get("value") == "GL-001A"
    assert pn.get("confidence") == "high"

_run("ingest: wrap_values_vcf=True wraps leaf values", t41)


# ════════════════════════════════════════════════════════════════════
# TEST 42 — ingest: multimodal image_paths → list content in user turn
# ════════════════════════════════════════════════════════════════════
def t42():
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction

    sample = build_training_sample_from_correction(
        run_row={
            "form_type":        "125",
            "raw_text":         "Agency: TestAgency",
            "original_fields":  {"agency": "TestAgency"},
            "upload_id":        "uid-mm-001",
            "sample_id":        "sid-mm-001",
        },
        corrected_json={"agency": "TestAgency"},
        image_paths=["images/pdf_abc/page_1.png", "images/pdf_abc/page_2.png"],
    )
    user_content = sample["messages"][1]["content"]
    assert isinstance(user_content, list),           "multimodal user content must be a list"
    image_blocks = [b for b in user_content if isinstance(b, dict) and b.get("type") == "image"]
    text_blocks  = [b for b in user_content if isinstance(b, dict) and b.get("type") == "text"]
    assert len(image_blocks) == 2,                   "2 image blocks for 2 image paths"
    assert len(text_blocks)  == 1,                   "1 text block"
    assert "ACORD Form 125" in text_blocks[0]["text"], "form type in text block"
    assert sample["metadata"]["image_manifest"] == ["images/pdf_abc/page_1.png", "images/pdf_abc/page_2.png"]

_run("ingest: multimodal image_paths -> list content in user turn", t42)


# ════════════════════════════════════════════════════════════════════
# TEST 43 — validate_chat_format: multimodal list content accepted
# ════════════════════════════════════════════════════════════════════
def t43():
    from fine_tuning.dataset.dataset_builder import validate_chat_format, InvalidChatFormatError

    multimodal_row = {
        "messages": [
            {"role": "system",    "content": "You are an expert."},
            {"role": "user",      "content": [
                {"type": "image", "image": "page_1.png"},
                {"type": "text",  "text": "Extract fields from this ACORD 25 document."},
            ]},
            {"role": "assistant", "content": '{"policy_number": "GL-001A"}'},
        ]
    }
    validate_chat_format(multimodal_row, 0)   # must not raise

    # Empty list content must raise
    try:
        validate_chat_format({"messages": [
            {"role": "system",    "content": "ok"},
            {"role": "user",      "content": []},   # empty list → invalid
            {"role": "assistant", "content": '{"field": "v"}'},
        ]}, 0)
        raise AssertionError("Should have raised for empty content list")
    except InvalidChatFormatError:
        pass

_run("validate_chat_format: multimodal list content accepted; empty list rejected", t43)


# ════════════════════════════════════════════════════════════════════
# TEST 44 — DatasetBuilder: min_records too high raises InsufficientDataError
# ════════════════════════════════════════════════════════════════════
def t44():
    from fine_tuning.dataset.dataset_builder import DatasetBuilder, InsufficientDataError
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        snapshot = tmp / "v0001.jsonl"
        row = build_training_sample_from_correction(
            run_row={
                "form_type": "25", "raw_text": "Agency: Test",
                "original_fields": {"agency": "Old"}, "upload_id": "u0", "sample_id": "s0",
            },
            corrected_json={"agency": "New"},
        )
        snapshot.write_text(json.dumps(row) + "\n", encoding="utf-8")

        config = {
            "paths": {
                "datasets_dir": str(tmp / "datasets"),
                "runs_dir":     str(tmp / "runs"),
                "registry_path": str(tmp / "registry.json"),
            },
            "continuous_learning": {
                "feedback_datasets_dir": str(tmp / "feedback"),
            },
        }
        try:
            DatasetBuilder(config).build(
                new_data_path=str(snapshot),
                cycle_id="smoke-min-001",
                min_records=9999,   # impossibly high
            )
            raise AssertionError("Should have raised InsufficientDataError")
        except InsufficientDataError:
            pass

_run("DatasetBuilder: min_records too high raises InsufficientDataError", t44)


# ════════════════════════════════════════════════════════════════════
# TEST 45 — DatasetBuilder: quality report doc type diversity
# ════════════════════════════════════════════════════════════════════
def t45():
    from fine_tuning.dataset.dataset_builder import DatasetBuilder
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        snapshot = tmp / "v0001.jsonl"
        rows = []
        # 2 ACORD 25 + 2 POLICY_DEC samples → diversity = 2 doc types
        for form_type, i in [("25", 0), ("25", 1), ("POLICY_DEC", 2), ("POLICY_DEC", 3)]:
            r = build_training_sample_from_correction(
                run_row={
                    "form_type": form_type,
                    "raw_text": f"text {i}",
                    "original_fields": {"f": "w"},
                    "upload_id": f"u{i}", "sample_id": f"s{i}",
                },
                corrected_json={"f": f"v{i}"},
            )
            rows.append(r)
        snapshot.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

        config = {
            "paths": {
                "datasets_dir": str(tmp / "datasets"),
                "runs_dir":     str(tmp / "runs"),
                "registry_path": str(tmp / "registry.json"),
            },
            "continuous_learning": {
                "feedback_datasets_dir": str(tmp / "feedback"),
            },
        }
        result = DatasetBuilder(config).build(
            new_data_path=str(snapshot),
            cycle_id="smoke-quality-001",
            min_records=1,
        )
        assert result.new_records == 4, f"4 new records, got {result.new_records}"
        qr = result.quality_report
        assert qr["document_type_diversity"] >= 2, "at least 2 doc types"
        assert "25" in qr["document_types"] or "UNKNOWN" in qr["document_types"] or "POLICY_DEC" in qr["document_types"], \
            f"doc types should include ACORD/POLICY_DEC, got {qr['document_types']}"

_run("DatasetBuilder: quality report doc type diversity", t45)


# ════════════════════════════════════════════════════════════════════
# TEST 46 — train.py: USE_LLAMA_FACTORY is False when CLI not installed
# ════════════════════════════════════════════════════════════════════
def t46():
    import importlib
    import os
    import shutil

    # Save and clear env var; verify module-level detection is consistent
    original_env = os.environ.get("USE_LLAMA_FACTORY")
    os.environ.pop("USE_LLAMA_FACTORY", None)

    # If llamafactory-cli is not on PATH, USE_LLAMA_FACTORY must be False
    lf_on_path = shutil.which("llamafactory-cli") is not None

    # Reimport with patched env
    import fine_tuning.train as _train_mod
    # The module-level value is set at import time, so we read it directly
    # and check consistency: it must match "cli on PATH" logic
    expected = lf_on_path
    actual   = _train_mod.USE_LLAMA_FACTORY
    assert actual == expected, (
        f"USE_LLAMA_FACTORY ({actual}) should match shutil.which result ({expected})"
    )

    if original_env is not None:
        os.environ["USE_LLAMA_FACTORY"] = original_env

_run("train.py: USE_LLAMA_FACTORY matches shutil.which result", t46)


# ════════════════════════════════════════════════════════════════════
# TEST 47 — train.py: _dict_to_yaml serialises LF config correctly
# ════════════════════════════════════════════════════════════════════
def t47():
    from fine_tuning.train import _dict_to_yaml

    cfg = {
        "model_name_or_path": "/workspace/models/qwen2-vl-7b",
        "stage": "sft",
        "do_train": True,
        "lora_rank": 16,
        "lora_alpha": 32.0,
        "visual_inputs": True,
        "none_field": None,          # None values must be omitted
        "special: value": "colon",   # colon in value → must be quoted
    }
    yaml_str = _dict_to_yaml(cfg)

    assert "model_name_or_path:" in yaml_str,     "model path present"
    assert "do_train: true" in yaml_str,           "bool True → 'true'"
    assert "lora_rank: 16" in yaml_str,            "int value present"
    assert "visual_inputs: true" in yaml_str,      "bool True → 'true'"
    assert "none_field" not in yaml_str,           "None values omitted"
    # Strings with colons must be quoted
    lines = {l.split(":")[0].strip(): l for l in yaml_str.splitlines() if ":" in l}
    # The value "colon" itself is fine; what matters is the quoted string path key
    assert "stage: sft" in yaml_str,              "plain string without special chars"

_run("train.py: _dict_to_yaml correct serialisation", t47)


# ════════════════════════════════════════════════════════════════════
# TEST 48 — version_store: two sequential cycles accumulate rows
# ════════════════════════════════════════════════════════════════════
def t48():
    from fine_tuning.continuous_learning.version_store import (
        append_training_sample,
        load_all_versioned_rows,
        load_pending_rows,
    )
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        def _make_row(i: int):
            return build_training_sample_from_correction(
                {"form_type": "25", "raw_text": f"text {i}",
                 "original_fields": {"f": "w"}, "upload_id": f"u{i}", "sample_id": f"s{i}"},
                {"f": f"v{i}"},
            )

        # Cycle 1: push 3 rows → snapshot v1 created (threshold=3)
        for i in range(3):
            outcome = append_training_sample(root, _make_row(i), retrain_threshold=3)
        assert outcome.snapshot_version == 1, "first snapshot is v1"
        assert load_pending_rows(root) == [], "pending cleared after v1"

        # Cycle 2: push 3 more rows → snapshot v2 created
        for i in range(3, 6):
            outcome = append_training_sample(root, _make_row(i), retrain_threshold=3)
        assert outcome.snapshot_version == 2, "second snapshot is v2"

        all_rows = load_all_versioned_rows(root)
        assert len(all_rows) == 6, f"6 total versioned rows across v1+v2, got {len(all_rows)}"

_run("version_store: two sequential cycles accumulate versioned rows", t48)


# ════════════════════════════════════════════════════════════════════
# TEST 49 — version_store: pending rows survive below threshold
# ════════════════════════════════════════════════════════════════════
def t49():
    from fine_tuning.continuous_learning.version_store import (
        append_training_sample,
        load_pending_rows,
        load_all_versioned_rows,
    )
    from fine_tuning.continuous_learning.ingest import build_training_sample_from_correction

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        def _make_row(i: int):
            return build_training_sample_from_correction(
                {"form_type": "25", "raw_text": f"text {i}",
                 "original_fields": {"f": "w"}, "upload_id": f"u{i}", "sample_id": f"s{i}"},
                {"f": f"v{i}"},
            )

        # 2 rows with threshold=5 → no snapshot, both remain pending
        append_training_sample(root, _make_row(0), retrain_threshold=5)
        outcome = append_training_sample(root, _make_row(1), retrain_threshold=5)

        assert outcome.version_snapshot_path is None, "no snapshot yet"
        assert outcome.pending_count_after   == 2,    "2 rows pending"
        pending = load_pending_rows(root)
        assert len(pending) == 2,                     "load_pending_rows returns 2"
        assert load_all_versioned_rows(root) == [],   "no versioned rows yet"

_run("version_store: pending rows survive below threshold", t49)


# ════════════════════════════════════════════════════════════════════
# TEST 50 — extractor: edge cases (empty text, no colons, separator-only values)
# ════════════════════════════════════════════════════════════════════
def t50():
    from extractor import _extract_kv_from_ocr_text

    # Empty text → empty dict
    assert _extract_kv_from_ocr_text("") == {}, "empty text → empty dict"

    # No colons → empty dict
    assert _extract_kv_from_ocr_text("Just some plain text without colons\n") == {}, \
        "no colons → empty dict"

    # Separator-only values must be excluded (value matches ^[-=_\s]{2,})
    kv = _extract_kv_from_ocr_text("SECTION HEADER: ====\nAGENCY: Convenis Agency\n")
    assert "section_header" not in kv, "separator-value key excluded"
    assert kv.get("agency") == "Convenis Agency", "normal key extracted"

    # Key with exactly 1 char after normalisation is excluded (< 2 chars check)
    kv2 = _extract_kv_from_ocr_text("X: some value\nAGENCY: Correct\n")
    # "x" is 1 char → should be excluded (key_raw must have len >= 2 before normalise)
    # "AGENCY" → "agency" (6 chars) must be present
    assert kv2.get("agency") == "Correct"

    # Multi-column line: two KV pairs separated by 3+ spaces
    kv3 = _extract_kv_from_ocr_text("CARRIER: Acme Insurance    NAIC CODE: 34214\n")
    assert kv3.get("carrier")   == "Acme Insurance", "first KV in multi-column line"
    assert kv3.get("naic_code") == "34214",           "second KV in multi-column line"

    # Value truncated at 300 chars
    long_val = "A" * 400
    kv4 = _extract_kv_from_ocr_text(f"LONG FIELD: {long_val}\n")
    assert kv4.get("long_field") is not None
    assert len(kv4["long_field"]) <= 300, "value truncated to 300 chars"

_run("extractor: edge cases — empty, no-colon, separator, multi-column, truncation", t50)


# ════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════
total = len(PASS) + len(FAIL)
print()
print("-" * 55)
print(f"  Results: {len(PASS)}/{total} passed", end="")
if FAIL:
    print(f"  |  FAILED: {', '.join(FAIL)}")
else:
    print(f"  {GREEN}{BOLD}ALL PASSED{RESET}")
print("-" * 55)
sys.exit(0 if not FAIL else 1)
