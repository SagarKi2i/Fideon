from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    text: str
    page: int = 1
    bbox: list[float] | None = Field(default=None, description="[x0,y0,x1,y1] in page coordinates")
    source: Literal["pdf_text", "ocr", "azure_di", "docx", "xlsx", "csv", "txt"] = "pdf_text"


class KeyValue(BaseModel):
    key: str
    value: str
    page: int = 1
    key_bbox: list[float] | None = None
    value_bbox: list[float] | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class Table(BaseModel):
    page: int = 1
    bbox: list[float] | None = None
    rows: list[list[str]] = Field(default_factory=list)


class PageLayout(BaseModel):
    page: int
    width: float | None = None
    height: float | None = None


class UnifiedIntermediateRepresentation(BaseModel):
    text_blocks: list[TextBlock] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    key_values: list[KeyValue] = Field(default_factory=list)
    layout: dict[str, Any] = Field(default_factory=dict)

