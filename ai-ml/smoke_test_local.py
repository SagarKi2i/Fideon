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
