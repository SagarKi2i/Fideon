from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class AcordExtractResponse(BaseModel):
    run_id: str = ""
    status: str = "draft"
    overall_confidence: float = 0.0
    extracted: dict[str, Any] = Field(default_factory=dict)
    # True when extraction succeeded but saving the draft run (or similar) failed — still return extracted.
    partial: bool = False
    persist_error: Optional[str] = None
    warning: Optional[str] = Field(
        default=None,
        description="Human-readable note (e.g. DB unavailable; submit may be disabled until saved).",
    )


class AcordSubmitRequest(BaseModel):
    thumbs_up: bool = Field(..., description="User validation signal")
    require_admin_approval_for_training: bool = Field(
        default=False,
        description="If true, route to admin queue even for high-confidence thumbs_up submissions.",
    )
    notes: Optional[str] = None
    corrected_json: Optional[dict[str, Any]] = Field(
        default=None, description="User-corrected extracted fields"
    )


class AcordAdminReviewRequest(BaseModel):
    decision: str = Field(..., description="approve|rework|reject")
    notes: Optional[str] = None
    corrected_json: Optional[dict[str, Any]] = None
    assigned_to: Optional[str] = None


class AcordBatchReviewRequest(BaseModel):
    run_ids: list[str] = Field(..., min_length=1, max_length=50)
    decision: str = Field(..., description="approve|reject")
    notes: Optional[str] = None


class ReExtractRequest(BaseModel):
    form_type_hint: Optional[str] = Field(
        default=None,
        description="e.g. '25', '125' — overrides the original form type hint",
    )


class AcordExtractStartResponse(BaseModel):
    job_id: str
    status: str = "queued"


class AcordExtractJobStatusResponse(BaseModel):
    job_id: str
    status: str = Field(..., description="queued|running|succeeded|failed")
    phase: Optional[str] = Field(
        default=None,
        description="queued|warming_model|generate_extracting|completed|failed",
    )
    result: Optional[AcordExtractResponse] = None
    error: Optional[str] = None


class PreviewSftTrainingRecordBody(BaseModel):
    """Mirrors `fine_tuning.export_approved_acord_dataset.build_training_jsonl_record` input."""

    extracted_json: dict[str, Any] = Field(default_factory=dict)
    raw_text: str = ""
    source_filename: Optional[str] = None

