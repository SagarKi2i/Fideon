"""
Optional Azure AI Document Intelligence (prebuilt-layout) for PDF text + tables.

Requires httpx (already a project dependency). Set in the environment:

  AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT  — e.g. https://<resource>.cognitiveservices.azure.com
  AZURE_DOCUMENT_INTELLIGENCE_KEY       — subscription key

Optional:

  AZURE_DOCUMENT_INTELLIGENCE_MODEL       — default prebuilt-layout
  AZURE_DOCUMENT_INTELLIGENCE_API_VERSION — default 2024-11-30
  AZURE_DOCUMENT_INTELLIGENCE_PAGES       — e.g. 1-20 (matches other ACORD PDF caps)
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any, Optional

import httpx

from .uir import Table, TextBlock, UnifiedIntermediateRepresentation

logger = logging.getLogger("fideon.azure_di")

_DEFAULT_API_VERSION = "2024-11-30"
_DEFAULT_MODEL = "prebuilt-layout"
_DEFAULT_PAGES = "1-20"
_MAX_POLL_ATTEMPTS = 200
_POLL_SLEEP_SEC = 1.0


def _table_to_rows(table: dict[str, Any]) -> tuple[int, list[list[str]]]:
    rc = int(table.get("rowCount") or 0)
    cc = int(table.get("columnCount") or 0)
    grid: list[list[str]] = [["" for _ in range(cc)] for _ in range(rc)]
    for cell in table.get("cells") or []:
        r_idx = cell.get("rowIndex")
        c_idx = cell.get("columnIndex")
        if r_idx is None or c_idx is None:
            continue
        if 0 <= r_idx < rc and 0 <= c_idx < cc:
            grid[r_idx][c_idx] = (cell.get("content") or "").strip()
    brs = table.get("boundingRegions") or []
    page = 1
    if brs and isinstance(brs[0], dict):
        page = int(brs[0].get("pageNumber") or 1)
    return page, grid


def _uir_from_analyze_result(data: dict[str, Any]) -> UnifiedIntermediateRepresentation | None:
    ar = data.get("analyzeResult") or {}
    content = (ar.get("content") or "").strip()
    tables_out: list[Table] = []
    for t in ar.get("tables") or []:
        if not isinstance(t, dict):
            continue
        page, rows = _table_to_rows(t)
        if rows and any(any(c for c in row) for row in rows):
            tables_out.append(Table(page=page, bbox=None, rows=rows))

    if not content and not tables_out:
        return None

    blocks: list[TextBlock] = []
    if content:
        blocks.append(
            TextBlock(text=content, page=1, bbox=None, source="azure_di"),
        )
    return UnifiedIntermediateRepresentation(
        text_blocks=blocks,
        tables=tables_out,
        layout={"extraction_engine": "azure_di"},
    )


async def try_azure_document_intelligence_to_uir(pdf_bytes: bytes) -> Optional[UnifiedIntermediateRepresentation]:
    """
    Call Document Intelligence prebuilt-layout on PDF bytes; return UIR or None if skipped/failed.

    Returns None when credentials are missing, request fails, or analysis yields no text/tables.
    """
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "").strip()
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "").strip()
    if not endpoint or not key:
        return None

    model = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    api_version = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_API_VERSION", _DEFAULT_API_VERSION).strip() or _DEFAULT_API_VERSION
    pages = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_PAGES", _DEFAULT_PAGES).strip() or _DEFAULT_PAGES

    e = endpoint.rstrip("/")
    post_path = f"{e}/documentintelligence/documentModels/{model}:analyze"
    params = {
        "api-version": api_version,
        "stringIndexType": "textElements",
        "pages": pages,
    }

    b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(300.0, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            post = await client.post(post_path, headers=headers, params=params, json={"base64Source": b64})
        except Exception as exc:
            logger.warning("Azure DI POST failed: %s", exc)
            return None

        if post.status_code != 202:
            body = (post.text or "")[:800]
            logger.warning("Azure DI analyze rejected: %s %s", post.status_code, body)
            return None

        op_loc = post.headers.get("Operation-Location") or post.headers.get("operation-location")
        if not op_loc:
            logger.warning("Azure DI missing Operation-Location header")
            return None

        initial_wait = float(post.headers.get("Retry-After") or 0.0)
        await asyncio.sleep(max(0.0, min(initial_wait, 30.0)))

        result: dict[str, Any] | None = None
        for attempt in range(_MAX_POLL_ATTEMPTS):
            if attempt > 0:
                await asyncio.sleep(_POLL_SLEEP_SEC)
            try:
                gr = await client.get(op_loc, headers={"Ocp-Apim-Subscription-Key": key})
            except Exception as exc:
                logger.warning("Azure DI poll GET failed: %s", exc)
                return None
            if gr.status_code != 200:
                logger.warning("Azure DI poll HTTP %s: %s", gr.status_code, (gr.text or "")[:400])
                return None
            payload = gr.json()
            status = (payload.get("status") or "").lower()
            if status == "succeeded":
                result = payload
                break
            if status == "failed":
                err = payload.get("error") or {}
                logger.warning("Azure DI analysis failed: %s", err)
                return None

        if result is None:
            logger.warning("Azure DI timed out after %d polls", _MAX_POLL_ATTEMPTS)
            return None

    uir = _uir_from_analyze_result(result)
    if uir is None:
        logger.info("Azure DI returned empty content and no tables")
    return uir
