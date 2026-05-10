from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class PodExtractResponse(BaseModel):
    run_id: str
    status: str
    overall_confidence: float = 0.0
    extracted: dict[str, Any] = Field(default_factory=dict)


class PodSubmitRequest(BaseModel):
    thumbs_up: bool = Field(..., description="User validation signal")
    require_admin_approval_for_training: bool = Field(
        default=False,
        description="If true, route to admin queue even for high-confidence thumbs_up submissions.",
    )
    notes: Optional[str] = None
    corrected_json: Optional[dict[str, Any]] = Field(
        default=None,
        description="User-corrected extracted fields",
    )


class PodAdminReviewRequest(BaseModel):
    decision: str = Field(..., description="approve|rework|reject")
    notes: Optional[str] = None
    corrected_json: Optional[dict[str, Any]] = None
    assigned_to: Optional[str] = None


class PodBatchReviewRequest(BaseModel):
    run_ids: list[str] = Field(..., min_length=1, max_length=50)
    decision: str = Field(..., description="approve|reject")
    notes: Optional[str] = None


class PodReExtractRequest(BaseModel):
    extraction_hint: Optional[str] = Field(
        default=None,
        description="Optional hint to guide extraction (pod-specific).",
    )

