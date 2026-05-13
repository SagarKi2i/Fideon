"""
test_universal_pipeline.py

Validates the universal insurance document training pipeline end-to-end:
    SchemaRegistry  → ingest.build_training_sample_from_correction
                    → DatasetBuilder.build

No GPU required — every test exercises pure-Python logic only.
Run with: pytest ai-ml/tests/test_universal_pipeline.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make ai-ml/ importable when running from the repo root or from this directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from insurance_schema_registry import (
    DocumentType,
    SchemaRegistry,
    get_registry,
    validate_currency_amount,
    validate_insurance_date,
    validate_naic_code,
    validate_phone_number,
    validate_policy_number,
)
from fine_tuning.continuous_learning.ingest import (
    CorrectionValidationError,
    build_training_sample_from_correction,
    get_corrected_paths,
    get_universal_system_prompt,
)
from fine_tuning.dataset.dataset_builder import (
    DatasetBuilder,
    InvalidChatFormatError,
    validate_chat_format,
    parse_assistant_fields,
)
from fine_tuning.continuous_learning.ingest import _normalize_fields_to_vcf
from fine_tuning.dataset.augmentor import AugmentorConfig, DataAugmentor


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def registry() -> SchemaRegistry:
    return SchemaRegistry()


@pytest.fixture
def valid_acord_25_json() -> dict:
    """Minimal ACORD 25 JSON that satisfies every required field."""
    return {
        "document_identification": {
            "document_type": "ACORD_25",
            "page_count": 1,
        },
        "parties": {
            "named_insured": "XYZ Construction Corp",
            "certificate_holder": "ABC Project Owner LLC",
        },
        "policy_identifiers": {
            "certificate_number": "CERT-2026-001",
        },
        "dates": {
            "effective_date": "2026-01-01",
            "expiration_date": "2027-01-01",
        },
        "coverages": [
            {"coverage_type": "General Liability", "limit": "$1,000,000"},
        ],
    }


@pytest.fixture
def valid_policy_dec_json() -> dict:
    return {
        "document_identification": {
            "document_type": "POLICY_DEC",
            "page_count": 2,
        },
        "parties": {
            "named_insured": "ABC Company LLC",
            "insurer": "National Insurance Co",
        },
        "policy_identifiers": {
            "policy_number": "CP-789456",
        },
        "dates": {
            "effective_date": "2026-01-01",
            "expiration_date": "2027-01-01",
        },
        "coverages": [
            {"coverage_type": "Commercial Property"},
        ],
        "financials": {
            "premium_total": "$5,420.00",
        },
    }


@pytest.fixture
def valid_loss_run_json() -> dict:
    return {
        "document_identification": {
            "document_type": "LOSS_RUN",
            "page_count": 1,
        },
        "parties": {
            "named_insured": "XYZ Corp",
            "insurer": "General Insurance Co",
        },
        "policy_identifiers": {
            "policy_number": "GL-123456",
        },
        "additional_fields": {
            "claims": [
                {
                    "claim_number": "2023-001",
                    "date_of_loss": "2023-03-15",
                    "status": "Closed",
                    "paid_amount": "$15,000",
                },
            ],
        },
    }


# ── Field validators ──────────────────────────────────────────────────────────

class TestFieldValidators:

    def test_policy_number_valid(self):
        assert validate_policy_number("GL-123456")
        assert validate_policy_number("CP-789")   # 4+ chars with letter + digit
        assert validate_policy_number("WC1234")

    def test_policy_number_invalid(self):
        assert not validate_policy_number("")
        assert not validate_policy_number("1234")   # no letter
        assert not validate_policy_number("ABC")    # no digit
        assert not validate_policy_number("GL")     # too short (< 4 chars)

    def test_naic_code_valid(self):
        assert validate_naic_code("20443")
        assert validate_naic_code("1234")

    def test_naic_code_invalid(self):
        assert not validate_naic_code("123")     # 3 digits — too short
        assert not validate_naic_code("123456")  # 6 digits — too long
        assert not validate_naic_code("2O443")   # contains letter O

    def test_insurance_date_valid(self):
        assert validate_insurance_date("2026-01-01")    # ISO
        assert validate_insurance_date("01/15/2026")    # MM/DD/YYYY
        assert validate_insurance_date("01-15-2026")    # MM-DD-YYYY

    def test_insurance_date_invalid(self):
        assert not validate_insurance_date("2026/1/1")  # no leading zeros
        assert not validate_insurance_date("not a date")
        assert not validate_insurance_date("")

    def test_currency_amount_valid(self):
        assert validate_currency_amount("$1,000,000")
        assert validate_currency_amount("5420.00")
        assert validate_currency_amount("$5,420.00")

    def test_currency_amount_invalid(self):
        assert not validate_currency_amount("one million")
        assert not validate_currency_amount("")

    def test_phone_number_valid(self):
        assert validate_phone_number("(555) 123-4567")
        assert validate_phone_number("5551234567")
        assert validate_phone_number("+1-800-555-0123")

    def test_phone_number_invalid(self):
        assert not validate_phone_number("12345")   # fewer than 7 digits
        assert not validate_phone_number("")


# ── Document type detection ───────────────────────────────────────────────────

class TestDocumentTypeDetection:
    """
    SchemaRegistry.detect_document_type() reads document_identification.document_type
    from the extracted JSON dict. There is no text-based detection function.
    """

    def test_detect_acord_25(self, registry):
        dt = registry.detect_document_type(
            {"document_identification": {"document_type": "ACORD_25", "page_count": 1}}
        )
        assert dt == DocumentType.ACORD_25

    def test_detect_acord_25_via_alias(self, registry):
        # "ACORD 25" (with space) is an accepted alias
        dt = registry.detect_document_type(
            {"document_identification": {"document_type": "ACORD 25", "page_count": 1}}
        )
        assert dt == DocumentType.ACORD_25

    def test_detect_policy_dec(self, registry):
        dt = registry.detect_document_type(
            {"document_identification": {"document_type": "POLICY_DEC", "page_count": 2}}
        )
        assert dt == DocumentType.POLICY_DEC

    def test_detect_policy_dec_via_declarations_alias(self, registry):
        dt = registry.detect_document_type(
            {"document_identification": {"document_type": "DECLARATIONS", "page_count": 2}}
        )
        assert dt == DocumentType.POLICY_DEC

    def test_detect_loss_run(self, registry):
        dt = registry.detect_document_type(
            {"document_identification": {"document_type": "LOSS_RUN", "page_count": 1}}
        )
        assert dt == DocumentType.LOSS_RUN

    def test_detect_loss_run_via_alias(self, registry):
        # "LOSS RUN" (with space) is an accepted alias
        dt = registry.detect_document_type(
            {"document_identification": {"document_type": "LOSS RUN", "page_count": 1}}
        )
        assert dt == DocumentType.LOSS_RUN

    def test_detect_missing_doc_id_returns_other(self, registry):
        # No document_identification key at all
        dt = registry.detect_document_type({"parties": {"named_insured": "Test"}})
        assert dt == DocumentType.OTHER

    def test_detect_unrecognised_type_returns_other(self, registry):
        dt = registry.detect_document_type(
            {"document_identification": {"document_type": "COMPLETELY_UNKNOWN", "page_count": 1}}
        )
        assert dt == DocumentType.OTHER

    def test_get_registry_singleton(self):
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2


# ── Schema validation ─────────────────────────────────────────────────────────

class TestSchemaValidation:

    def test_validate_acord_25_complete(self, registry, valid_acord_25_json):
        result = registry.validate(valid_acord_25_json)
        assert result["valid"] is True, f"Unexpected errors: {result['errors']}"
        assert result["document_type"] == "ACORD_25"
        assert result["missing_required"] == []

    def test_validate_policy_dec_complete(self, registry, valid_policy_dec_json):
        result = registry.validate(valid_policy_dec_json)
        assert result["valid"] is True, f"Unexpected errors: {result['errors']}"
        assert result["document_type"] == "POLICY_DEC"

    def test_validate_loss_run_complete(self, registry, valid_loss_run_json):
        result = registry.validate(valid_loss_run_json)
        assert result["valid"] is True, f"Unexpected errors: {result['errors']}"
        assert result["document_type"] == "LOSS_RUN"

    def test_validate_acord_25_missing_certificate_holder(self, registry):
        doc = {
            "document_identification": {"document_type": "ACORD_25", "page_count": 1},
            "parties": {"named_insured": "XYZ Corp"},  # certificate_holder missing
            "policy_identifiers": {"certificate_number": "CERT-001"},
            "dates": {"effective_date": "2026-01-01", "expiration_date": "2027-01-01"},
            "coverages": [{"coverage_type": "GL", "limit": "$1,000,000"}],
        }
        result = registry.validate(doc)
        assert result["valid"] is False
        assert any("certificate_holder" in p for p in result["missing_required"])

    def test_validate_missing_document_identification(self, registry):
        # The only required top-level section is document_identification
        doc = {"parties": {"named_insured": "Test Corp"}}
        result = registry.validate(doc)
        assert result["valid"] is False
        assert "document_identification" in result["missing_required"]

    def test_validate_missing_parties(self, registry):
        # parties is required and must have ≥1 non-empty field
        doc = {
            "document_identification": {"document_type": "OTHER", "page_count": 1},
            # parties absent
        }
        result = registry.validate(doc)
        assert result["valid"] is False
        assert "parties" in result["missing_required"]

    def test_validate_non_dict_returns_invalid(self, registry):
        result = registry.validate("not a dict")  # type: ignore[arg-type]
        assert result["valid"] is False
        assert result["document_type"] == "UNKNOWN"

    def test_validate_result_has_required_keys(self, registry, valid_acord_25_json):
        result = registry.validate(valid_acord_25_json)
        for key in ("valid", "document_type", "errors", "warnings", "missing_required", "field_stats"):
            assert key in result, f"Missing key: {key}"

    def test_field_stats_populated(self, registry, valid_acord_25_json):
        result = registry.validate(valid_acord_25_json)
        stats = result["field_stats"]
        assert stats["total_fields_present"] > 0
        assert isinstance(stats["empty_fields"], int)
        assert isinstance(stats["format_errors"], int)

    def test_suggest_corrections_ocr_policy_number(self, registry):
        # "GLOOO" has NO digits at all — validate_policy_number returns False.
        # _suggest_policy_number then replaces O→0 to get "GL000" which passes.
        doc = {
            "document_identification": {"document_type": "OTHER", "page_count": 1},
            "parties": {"named_insured": "Test"},
            "policy_identifiers": {"policy_number": "GLOOO"},
        }
        result = registry.validate(doc)
        corrections = registry.suggest_corrections(doc, result)
        assert "policy_identifiers.policy_number" in corrections
        assert corrections["policy_identifiers.policy_number"] == "GL000"

    def test_suggest_corrections_valid_date_no_suggestion(self, registry):
        # MM/DD/YYYY and YYYY-MM-DD are BOTH accepted by validate_insurance_date,
        # so no correction is suggested for either format.
        doc = {
            "document_identification": {"document_type": "OTHER", "page_count": 1},
            "parties": {"named_insured": "Test"},
            "dates": {"effective_date": "04/01/2026"},
        }
        result = registry.validate(doc)
        corrections = registry.suggest_corrections(doc, result)
        # Already valid → no suggestion
        assert "dates.effective_date" not in corrections


# ── Training sample generation ────────────────────────────────────────────────

class TestTrainingSampleGeneration:

    def test_build_sample_for_acord_25(self):
        sample = build_training_sample_from_correction(
            sample_id="test-001",
            upload_id="upload-001",
            form_type="25",
            original_fields={"insured_name": "ABC Corp"},
            corrected_fields={"insured_name": "ABC Corporation"},
            raw_text="Sample OCR text from ACORD 25 form",
        )
        assert len(sample["messages"]) == 3
        assert sample["messages"][0]["role"] == "system"
        assert sample["messages"][1]["role"] == "user"
        assert sample["messages"][2]["role"] == "assistant"
        # _canonical_form_key("25") → "25", so document_type is "25"
        assert sample["metadata"]["document_type"] == "25"
        assert sample["metadata"]["form_type"] == "25"
        assert "ACORD Form 25" in sample["messages"][1]["content"]
        assert "SURYA OCR TEXT:" in sample["messages"][1]["content"]
        # Corrected value must appear in assistant FIELDS JSON
        assistant_json = parse_assistant_fields(sample["messages"][2]["content"])
        assert assistant_json["insured_name"] == "ABC Corporation"

    def test_build_sample_for_policy_dec(self):
        sample = build_training_sample_from_correction(
            sample_id="test-002",
            upload_id="upload-002",
            form_type="POLICY_DEC",
            original_fields={"policy_number": "CP-123"},
            corrected_fields={"policy_number": "CP-123456"},
            raw_text="Policy declarations text for test",
        )
        assert sample["metadata"]["document_type"] == "POLICY_DEC"
        assert "Policy Declarations" in sample["messages"][1]["content"]
        assistant_json = parse_assistant_fields(sample["messages"][2]["content"])
        assert assistant_json["policy_number"] == "CP-123456"

    def test_build_sample_for_loss_run(self):
        sample = build_training_sample_from_correction(
            sample_id="test-003",
            upload_id="upload-003",
            form_type="LOSS_RUN",
            original_fields={"claims": []},
            corrected_fields={"claims": [{"claim_number": "2024-001"}]},
            raw_text="Loss run report text for testing",
        )
        assert sample["metadata"]["document_type"] == "LOSS_RUN"
        assert "Loss Run" in sample["messages"][1]["content"]
        assistant_json = parse_assistant_fields(sample["messages"][2]["content"])
        assert assistant_json["claims"][0]["claim_number"] == "2024-001"

    def test_system_prompt_is_universal(self):
        sample = build_training_sample_from_correction(
            sample_id="t",
            upload_id="u",
            form_type="25",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="some text",
        )
        system_content = sample["messages"][0]["content"]
        assert "insurance document" in system_content.lower()
        assert system_content == get_universal_system_prompt()

    def test_docling_data_appended_to_user_message(self):
        sample = build_training_sample_from_correction(
            sample_id="t",
            upload_id="u",
            form_type="25",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="OCR text here",
            docling_data={
                "markdown": "## Policy Summary",
                "kv_pairs": {"Insured": "ABC Corp"},
                "tables": ["| Col1 | Col2 |\n|---|---|\n| A | B |"],
            },
        )
        user_content = sample["messages"][1]["content"]
        assert "DOCLING TEXT:" in user_content
        assert "## Policy Summary" in user_content
        assert "[Key-Value Pairs]" in user_content
        assert "Insured: ABC Corp" in user_content
        assert "[Tables]" in user_content

    def test_corrected_fields_paths_tracked(self):
        sample = build_training_sample_from_correction(
            sample_id="t",
            upload_id="u",
            form_type="25",
            original_fields={"insured_name": "Old", "policy_number": "GL-123"},
            corrected_fields={"insured_name": "New"},  # only insured_name changed
            raw_text="some text",
        )
        assert sample["metadata"]["corrected_fields"] == ["insured_name"]

    def test_backward_compat_run_row_style(self):
        """Old run_row dict calling convention must still work unchanged."""
        run_row = {
            "sample_id": "legacy-001",
            "upload_id": "upload-legacy",
            "form_type": "25",
            "original_fields": {"insured": "Old"},
            "corrected_fields": {"insured": "New"},
            "raw_text": "legacy ocr text",
        }
        sample = build_training_sample_from_correction(
            run_row=run_row,
            corrected_json={"insured": "New"},
        )
        assert len(sample["messages"]) == 3
        assert sample["metadata"]["sample_id"] == "legacy-001"
        assistant_json = parse_assistant_fields(sample["messages"][2]["content"])
        assert assistant_json["insured"] == "New"

    def test_empty_corrected_fields_raises(self):
        with pytest.raises(CorrectionValidationError):
            build_training_sample_from_correction(
                sample_id="t",
                upload_id="u",
                form_type="25",
                original_fields={},
                corrected_fields={},
                raw_text="some text",
            )

    def test_unsupported_form_type_raises(self):
        with pytest.raises(CorrectionValidationError):
            build_training_sample_from_correction(
                sample_id="t",
                upload_id="u",
                form_type="INVALID_TYPE_XYZ",
                original_fields={"x": "1"},
                corrected_fields={"x": "2"},
                raw_text="some text",
            )


# ── Corrected paths tracking ──────────────────────────────────────────────────

class TestCorrectedPaths:

    def test_flat_dict_changed_field(self):
        original  = {"a": "1", "b": "2", "c": "3"}
        corrected = {"a": "changed"}
        paths = get_corrected_paths(original, corrected)
        assert paths == ["a"]

    def test_nested_dict_changed_field(self):
        original  = {"parties": {"named_insured": "Old", "insurer": "X"}}
        corrected = {"parties": {"named_insured": "New"}}
        paths = get_corrected_paths(original, corrected)
        assert paths == ["parties.named_insured"]

    def test_nested_sibling_unchanged(self):
        original  = {"parties": {"named_insured": "Old", "insurer": "X"}}
        corrected = {"parties": {"named_insured": "New"}}
        paths = get_corrected_paths(original, corrected)
        # "insurer" was NOT in corrected so NOT in paths
        assert "parties.insurer" not in paths

    def test_no_changes_returns_empty(self):
        original  = {"a": "1", "b": "2"}
        corrected = {"a": "1", "b": "2"}
        assert get_corrected_paths(original, corrected) == []

    def test_new_field_in_corrected(self):
        original  = {"a": "1"}
        corrected = {"a": "1", "b": "new_field"}
        paths = get_corrected_paths(original, corrected)
        assert "b" in paths


# ── Dataset building ──────────────────────────────────────────────────────────

class TestDatasetBuilding:

    def _make_config(self, tmp_path: Path) -> dict:
        return {
            "paths": {
                "datasets_dir": str(tmp_path / "datasets"),
            },
            "continuous_learning": {
                "feedback_datasets_dir": str(tmp_path / "feedback"),
                "min_samples_per_doc_type": 1,
            },
        }

    def _write_chat_rows_jsonl(self, rows: list, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")

    def test_build_with_mixed_document_types(self, tmp_path):
        form_types = ["25", "125", "POLICY_DEC", "LOSS_RUN"]
        chat_rows = []
        for i, ft in enumerate(form_types):
            row = build_training_sample_from_correction(
                sample_id=f"test-{i}",
                upload_id=f"upload-{i}",
                form_type=ft,
                original_fields={"field": "original"},
                corrected_fields={"field": "corrected"},
                raw_text=f"Sample OCR text for document type {ft}",
            )
            chat_rows.append(row)

        new_data_path = tmp_path / "new_data.jsonl"
        self._write_chat_rows_jsonl(chat_rows, new_data_path)

        config  = self._make_config(tmp_path)
        builder = DatasetBuilder(config)
        result  = builder.build(new_data_path=str(new_data_path), cycle_id="test-cycle")

        # 70/20/10: new=4, replay=0 (no history), synthetic≥0
        assert result.new_records == 4
        assert result.replay_records == 0
        assert result.rejected_records == 0
        assert result.total_records == result.new_records + result.replay_records + result.synthetic_records

        # Quality report has document type distribution for the 4 new rows
        dist = result.quality_report["document_types"]
        assert dist.get("25", 0) >= 1
        assert dist.get("125", 0) >= 1
        assert dist.get("POLICY_DEC", 0) >= 1
        assert dist.get("LOSS_RUN", 0) >= 1

    def test_manifest_written_with_doc_type_distribution(self, tmp_path):
        chat_row = build_training_sample_from_correction(
            sample_id="s1",
            upload_id="u1",
            form_type="POLICY_DEC",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="Policy declarations OCR text",
        )
        new_data_path = tmp_path / "new_data.jsonl"
        self._write_chat_rows_jsonl([chat_row], new_data_path)

        config  = self._make_config(tmp_path)
        builder = DatasetBuilder(config)
        result  = builder.build(new_data_path=str(new_data_path), cycle_id="manifest-test")

        manifest_path = Path(config["paths"]["datasets_dir"]) / "cycle-manifest-test" / "dataset_manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert "document_type_distribution" in manifest
        assert manifest["document_type_distribution"]["POLICY_DEC"] == 1

    def test_quality_report_written(self, tmp_path):
        chat_row = build_training_sample_from_correction(
            sample_id="s1",
            upload_id="u1",
            form_type="25",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="Sample ACORD 25 OCR text",
        )
        new_data_path = tmp_path / "new_data.jsonl"
        self._write_chat_rows_jsonl([chat_row], new_data_path)

        config  = self._make_config(tmp_path)
        builder = DatasetBuilder(config)
        builder.build(new_data_path=str(new_data_path), cycle_id="quality-test")

        report_path = (
            Path(config["paths"]["datasets_dir"])
            / "cycle-quality-test"
            / "dataset_quality_report.json"
        )
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report["total_samples"] == 1
        assert report["document_type_diversity"] == 1
        assert isinstance(report["avg_fields_per_sample"], (int, float))

    def test_rejected_invalid_chat_format(self, tmp_path):
        good_row = build_training_sample_from_correction(
            sample_id="good",
            upload_id="u",
            form_type="25",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="Valid OCR text",
        )
        bad_row = {"messages": [{"role": "user", "content": "no assistant turn"}]}

        new_data_path = tmp_path / "new_data.jsonl"
        self._write_chat_rows_jsonl([good_row, bad_row], new_data_path)

        config  = self._make_config(tmp_path)
        builder = DatasetBuilder(config)
        result  = builder.build(new_data_path=str(new_data_path), cycle_id="reject-test")
        assert result.total_records == 1
        assert result.rejected_records == 1

    def test_validate_chat_format_rejects_non_json_assistant(self):
        row = {
            "messages": [
                {"role": "system", "content": "You are an expert."},
                {"role": "user", "content": "Extract this."},
                {"role": "assistant", "content": "This is not JSON at all."},
            ]
        }
        with pytest.raises(InvalidChatFormatError):
            validate_chat_format(row, 0)

    def test_validate_chat_format_accepts_valid_row(self):
        row = {
            "messages": [
                {"role": "system", "content": "You are an expert."},
                {"role": "user", "content": "Extract this."},
                {"role": "assistant", "content": '{"policy_number": "GL-123"}'},
            ]
        }
        validate_chat_format(row, 0)  # should not raise

    def test_validate_chat_format_accepts_fields_format(self):
        """validate_chat_format must accept the new FIELDS: assistant format."""
        row = {
            "messages": [
                {"role": "system", "content": "You are an expert."},
                {"role": "user", "content": "Extract this."},
                {"role": "assistant", "content": 'FIELDS:\n{"policy_number": "GL-123"}\n\nRAW TEXT:\npage text'},
            ]
        }
        validate_chat_format(row, 0)  # must not raise

    def test_build_assistant_content_uses_fields_format(self):
        """build_training_sample_from_correction always produces FIELDS: prefix."""
        sample = build_training_sample_from_correction(
            sample_id="fmt-001",
            upload_id="u-fmt",
            form_type="25",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="Some OCR text",
        )
        content = sample["messages"][2]["content"]
        assert content.startswith("FIELDS:"), f"Expected FIELDS: prefix, got: {content[:60]!r}"
        assert parse_assistant_fields(content) == {"x": "2"}

    def test_build_result_has_synthetic_records(self, tmp_path):
        """DatasetBuildResult.synthetic_records is populated from 70/20/10 split."""
        chat_rows = [
            build_training_sample_from_correction(
                sample_id=f"s{i}", upload_id=f"u{i}", form_type="25",
                original_fields={"x": "1"}, corrected_fields={"x": "2"},
                raw_text="text",
            )
            for i in range(7)
        ]
        new_data_path = tmp_path / "new_data.jsonl"
        self._write_chat_rows_jsonl(chat_rows, new_data_path)
        config  = self._make_config(tmp_path)
        result  = DatasetBuilder(config).build(str(new_data_path), "synth-test")
        assert result.synthetic_records >= 0
        assert result.total_records == result.new_records + result.replay_records + result.synthetic_records


# ── End-to-end flow (no GPU) ──────────────────────────────────────────────────

class TestEndToEndFlow:

    @pytest.mark.slow
    def test_full_pipeline_acord_25(self, registry):
        """Simulates correction → ingest → assistant JSON → schema validation."""
        # 1. Simulate original extraction and user correction
        extracted = {
            "document_type": "ACORD_25",
            "parties": {"named_insured": "Test Corp", "certificate_holder": ""},
        }
        corrected = {
            "document_type": "ACORD_25",
            "parties": {"named_insured": "Test Corporation", "certificate_holder": "Client LLC"},
        }

        # 2. Build training sample
        sample = build_training_sample_from_correction(
            sample_id="e2e-acord25",
            upload_id="e2e-upload",
            form_type="25",
            original_fields=extracted,
            corrected_fields=corrected,
            raw_text="Certificate of Liability Insurance ACORD 25 test text",
        )

        # 3. Verify structure
        assert len(sample["messages"]) == 3
        assert sample["domain"] == "insurance"

        # 4. Verify assistant JSON content
        assistant_json = parse_assistant_fields(sample["messages"][2]["content"])
        assert assistant_json["document_type"] == "ACORD_25"
        assert assistant_json["parties"]["named_insured"] == "Test Corporation"
        assert assistant_json["parties"]["certificate_holder"] == "Client LLC"

        # 5. Schema registry validates the merged JSON (OTHER type — flat structure)
        result = registry.validate(assistant_json)
        # The merged dict uses flat structure, so detected type is OTHER
        assert result["document_type"] == "OTHER"

    @pytest.mark.slow
    def test_full_pipeline_loss_run(self, registry):
        extracted = {"policy_number": "GL-O12345"}  # OCR error: O instead of 0
        corrected = {"policy_number": "GL-012345"}

        sample = build_training_sample_from_correction(
            sample_id="e2e-lossrun",
            upload_id="e2e-upload-2",
            form_type="LOSS_RUN",
            original_fields=extracted,
            corrected_fields=corrected,
            raw_text="Loss Run Report with claims data for testing",
        )

        assert "Loss Run" in sample["messages"][1]["content"]
        assistant_json = parse_assistant_fields(sample["messages"][2]["content"])
        assert assistant_json["policy_number"] == "GL-012345"
        # Verify corrected_fields tracking caught the change
        assert "policy_number" in sample["metadata"]["corrected_fields"]

    @pytest.mark.slow
    def test_universal_system_prompt_consistent(self):
        """Every sample, regardless of doc type, uses the same universal system prompt."""
        prompt = get_universal_system_prompt()
        for form_type in ("25", "125", "POLICY_DEC", "LOSS_RUN", "CERTIFICATE"):
            sample = build_training_sample_from_correction(
                sample_id="t",
                upload_id="u",
                form_type=form_type,
                original_fields={"x": "1"},
                corrected_fields={"x": "2"},
                raw_text="some text",
            )
            assert sample["messages"][0]["content"] == prompt


# ── Multimodal format (Gap 1 + Gap 2) ────────────────────────────────────────

class TestMultimodalFormat:

    def test_image_paths_produce_list_user_content(self):
        """When image_paths is provided, user.content must be a list of blocks."""
        sample = build_training_sample_from_correction(
            sample_id="mm-001",
            upload_id="upload-mm",
            form_type="25",
            original_fields={"insured": "Old"},
            corrected_fields={"insured": "New"},
            raw_text="ACORD 25 OCR text for multimodal test",
            image_paths=["images/upload-mm/page_1.png", "images/upload-mm/page_2.png"],
        )
        user_content = sample["messages"][1]["content"]
        assert isinstance(user_content, list), "user.content must be a list when image_paths provided"
        # First two items are image blocks
        assert user_content[0] == {"type": "image", "image": "images/upload-mm/page_1.png"}
        assert user_content[1] == {"type": "image", "image": "images/upload-mm/page_2.png"}
        # Last item is the text block
        assert user_content[-1]["type"] == "text"
        assert "ACORD Form 25" in user_content[-1]["text"]

    def test_no_image_paths_produces_string_user_content(self):
        """Without image_paths, user.content remains a plain string (backward compat)."""
        sample = build_training_sample_from_correction(
            sample_id="mm-002",
            upload_id="upload-mm",
            form_type="25",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="Some OCR text here with enough content",
        )
        assert isinstance(sample["messages"][1]["content"], str)

    def test_page_texts_format_per_page_ocr(self):
        """page_texts kwarg produces per-page OCR sections in user text."""
        sample = build_training_sample_from_correction(
            sample_id="mm-003",
            upload_id="u3",
            form_type="POLICY_DEC",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="fallback text",
            page_texts=["Page 1 content here", "Page 2 content here"],
        )
        content = sample["messages"][1]["content"]
        assert isinstance(content, str)
        assert "SURYA OCR TEXT:" in content
        assert "=== PAGE 1 ===" in content
        assert "Page 1 content here" in content
        assert "=== PAGE 2 ===" in content

    def test_metadata_includes_new_fields(self):
        """dataset_version, page_count, image_manifest, preprocessing all stored."""
        sample = build_training_sample_from_correction(
            sample_id="mm-004",
            upload_id="u4",
            form_type="25",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="Some OCR text for metadata test",
            image_paths=["images/u4/page_1.png"],
            page_count=1,
            dataset_version="v2",
            preprocessing={"ocr_engine": "surya", "dpi": 300},
        )
        meta = sample["metadata"]
        assert meta["dataset_version"] == "v2"
        assert meta["page_count"] == 1
        assert meta["image_manifest"] == ["images/u4/page_1.png"]
        assert meta["preprocessing"]["ocr_engine"] == "surya"

    def test_surya_page_texts_kwarg_produces_same_format(self):
        """surya_page_texts kwarg is the canonical alias for page_texts."""
        sample = build_training_sample_from_correction(
            sample_id="mm-surya",
            upload_id="u-surya",
            form_type="25",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="fallback",
            surya_page_texts=["Surya page 1 text", "Surya page 2 text"],
        )
        user_text = sample["messages"][1]["content"]
        assert "SURYA OCR TEXT:" in user_text
        assert "=== PAGE 1 ===" in user_text
        assert "Surya page 1 text" in user_text
        assert "=== PAGE 2 ===" in user_text
        # Assistant RAW TEXT section should also have per-page content
        asst = sample["messages"][2]["content"]
        assert "RAW TEXT:" in asst
        assert "=== PAGE 1 ===" in asst

    def test_validate_chat_format_accepts_list_user_content(self):
        """validate_chat_format must NOT raise for list user.content (Gap 2 fix)."""
        row = {
            "messages": [
                {"role": "system", "content": "System prompt."},
                {"role": "user",   "content": [
                    {"type": "image", "image": "images/u/page_1.png"},
                    {"type": "text",  "text": "OCR here."},
                ]},
                {"role": "assistant", "content": '{"policy_number": "GL-123"}'},
            ]
        }
        validate_chat_format(row, 0)  # must not raise

    def test_validate_chat_format_rejects_empty_list_content(self):
        """An empty list is not valid content."""
        row = {
            "messages": [
                {"role": "system", "content": "Prompt."},
                {"role": "user",   "content": []},          # empty list → invalid
                {"role": "assistant", "content": '{"x": "y"}'},
            ]
        }
        with pytest.raises(InvalidChatFormatError):
            validate_chat_format(row, 0)


# ── Value/page/confidence normalization (Gap 4) ───────────────────────────────

class TestVCFNormalization:

    def test_flat_scalars_wrapped(self):
        fields = {"policy_number": "GL-123", "named_insured": "Acme Corp"}
        result = _normalize_fields_to_vcf(fields)
        assert result["policy_number"] == {"value": "GL-123", "page": None, "confidence": "high"}
        assert result["named_insured"] == {"value": "Acme Corp", "page": None, "confidence": "high"}

    def test_already_wrapped_preserved(self):
        fields = {"policy_number": {"value": "GL-123", "page": 1, "confidence": "high"}}
        result = _normalize_fields_to_vcf(fields)
        assert result["policy_number"]["page"] == 1  # page must be preserved

    def test_nested_dict_recursed(self):
        fields = {"parties": {"named_insured": "Acme"}}
        result = _normalize_fields_to_vcf(fields)
        assert result["parties"]["named_insured"]["value"] == "Acme"

    def test_list_of_dicts_recursed(self):
        fields = {"coverages": [{"coverage_type": "GL", "limit": "$1M"}]}
        result = _normalize_fields_to_vcf(fields)
        assert result["coverages"][0]["coverage_type"]["value"] == "GL"

    def test_wrap_values_vcf_kwarg_in_ingest(self):
        """build_training_sample_from_correction(wrap_values_vcf=True) uses VCF wrapping."""
        sample = build_training_sample_from_correction(
            sample_id="vcf-001",
            upload_id="u-vcf",
            form_type="25",
            original_fields={"policy_number": "GL-123"},
            corrected_fields={"policy_number": "GL-456"},
            raw_text="Policy number test OCR text",
            wrap_values_vcf=True,
        )
        assistant_json = parse_assistant_fields(sample["messages"][2]["content"])
        pn = assistant_json.get("policy_number")
        assert isinstance(pn, dict), "Expected {value, page, confidence} wrapper"
        assert pn["value"] == "GL-456"
        assert "confidence" in pn


# ── Augmentor (Gap 8) ─────────────────────────────────────────────────────────

class TestAugmentor:

    def _make_row(self, form_type: str = "25") -> dict:
        return build_training_sample_from_correction(
            sample_id="aug-src",
            upload_id="u-aug",
            form_type=form_type,
            original_fields={"policy_number": "GL-123456"},
            corrected_fields={"policy_number": "GL-654321"},
            raw_text="Loss run report with policy GL-654321 for augmentation testing",
        )

    def test_augment_produces_correct_count(self):
        row = self._make_row()
        aug = DataAugmentor(AugmentorConfig(copies_per_sample=3, seed=0))
        result = aug.augment_dataset([row])
        assert len(result) == 3

    def test_augmented_rows_are_tagged(self):
        row = self._make_row()
        aug = DataAugmentor(AugmentorConfig(copies_per_sample=1, seed=1))
        result = aug.augment_dataset([row])
        assert result[0]["metadata"].get("augmented") is True

    def test_required_fields_never_blanked(self):
        """policy_number is in _REQUIRED_FIELD_NAMES — must survive dropout."""
        row = self._make_row()
        aug = DataAugmentor(AugmentorConfig(
            copies_per_sample=10, field_dropout_rate=1.0, seed=42  # max dropout
        ))
        for aug_row in aug.augment_dataset([row]):
            asst = parse_assistant_fields(aug_row["messages"][2]["content"])
            assert asst is not None
            assert asst.get("policy_number") not in (None, ""), \
                "policy_number must not be blanked by dropout"

    def test_augmented_assistant_json_still_valid(self):
        """Augmented assistant content must remain parseable JSON."""
        row = self._make_row()
        aug = DataAugmentor(AugmentorConfig(copies_per_sample=5, seed=7))
        for aug_row in aug.augment_dataset([row]):
            content = aug_row["messages"][2]["content"]
            parsed = parse_assistant_fields(content)
            assert parsed is not None and isinstance(parsed, dict)

    def test_multimodal_row_augmented_correctly(self):
        """Image blocks must be preserved; OCR noise applies only to text blocks."""
        row = build_training_sample_from_correction(
            sample_id="aug-mm",
            upload_id="u-aug-mm",
            form_type="25",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="OCR text for augmentation with images",
            image_paths=["images/u-aug-mm/page_1.png"],
        )
        aug = DataAugmentor(AugmentorConfig(copies_per_sample=1, seed=0))
        result = aug.augment_dataset([row])
        user_content = result[0]["messages"][1]["content"]
        assert isinstance(user_content, list)
        # Image block must be untouched
        image_blocks = [b for b in user_content if b.get("type") == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0]["image"] == "images/u-aug-mm/page_1.png"


# ── LLaMA-Factory data layout (Gap 9) ────────────────────────────────────────

class TestLlamaFactoryLayout:

    def test_data_dir_written_by_builder(self, tmp_path):
        """DatasetBuilder.build() must create data/train.jsonl + data/dataset_info.json."""
        chat_row = build_training_sample_from_correction(
            sample_id="lf-001",
            upload_id="u-lf",
            form_type="25",
            original_fields={"x": "1"},
            corrected_fields={"x": "2"},
            raw_text="LLaMA-Factory layout test OCR text",
        )
        new_data_path = tmp_path / "new_data.jsonl"
        new_data_path.parent.mkdir(parents=True, exist_ok=True)
        with new_data_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(chat_row) + "\n")

        config = {
            "paths": {"datasets_dir": str(tmp_path / "datasets")},
            "continuous_learning": {
                "feedback_datasets_dir": str(tmp_path / "feedback"),
                "min_samples_per_doc_type": 1,
            },
        }
        builder = DatasetBuilder(config)
        builder.build(new_data_path=str(new_data_path), cycle_id="lf-cycle")

        lf_dir = Path(config["paths"]["datasets_dir"]) / "cycle-lf-cycle" / "data"
        assert (lf_dir / "train.jsonl").exists(), "data/train.jsonl missing"
        assert (lf_dir / "dataset_info.json").exists(), "data/dataset_info.json missing"

        info = json.loads((lf_dir / "dataset_info.json").read_text())
        assert "fideon_insurance" in info
        assert info["fideon_insurance"]["file_name"] == "train.jsonl"


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate the universal insurance document pipeline"
    )
    parser.add_argument(
        "--validate-extraction",
        metavar="JSON_FILE",
        help="Path to an extracted JSON file to validate against the schema registry",
    )
    parser.add_argument(
        "--document-type",
        metavar="DOC_TYPE",
        help="Expected document type (informational; registry auto-detects from JSON)",
    )
    args = parser.parse_args()

    if args.validate_extraction:
        with open(args.validate_extraction, encoding="utf-8") as fh:
            extracted = json.load(fh)

        reg = SchemaRegistry()
        result = reg.validate(extracted)

        status = "PASS" if result["valid"] else "FAIL"
        print(f"\nValidation result : {status}")
        print(f"Detected type     : {result['document_type']}")
        if args.document_type:
            match = result["document_type"] == args.document_type.upper()
            print(f"Expected type     : {args.document_type}  {'✓' if match else '✗ MISMATCH'}")
        if result["errors"]:
            print(f"\nErrors ({len(result['errors'])}):")
            for e in result["errors"]:
                print(f"  - {e}")
        if result["warnings"]:
            print(f"\nWarnings ({len(result['warnings'])}):")
            for w in result["warnings"]:
                print(f"  - {w}")
        if result["missing_required"]:
            print(f"\nMissing required fields: {result['missing_required']}")
        corr = reg.suggest_corrections(extracted, result)
        if corr:
            print(f"\nSuggested OCR corrections:")
            for path, fix in corr.items():
                print(f"  {path}: {fix!r}")
    else:
        sys.exit(pytest.main([__file__, "-v"]))
