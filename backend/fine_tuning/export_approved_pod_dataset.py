"""
Export approved pod extraction runs from Supabase into a JSONL dataset for SFT/QLoRA.

This is the pod-generic replacement for `export_approved_acord_dataset.py`.

Usage (from backend directory, with backend/.env configured):
  python -m fine_tuning.export_approved_pod_dataset --out fine_tuning/data/approved_pod.jsonl --pod-id <pod_id>

To export a single approved run (used by automatic training trigger):
  python -m fine_tuning.export_approved_pod_dataset --run-id <uuid> --out fine_tuning/data/pod_<uuid>.jsonl --pod-id <pod_id>

Notes:
- The dataset format is compatible with `fine_tuning/train.py` and the shared dataset schema:
  required keys: `instruction`, `output`
  optional keys: `input`, `domain`, `metadata`
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

from app.core.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


async def _fetch_one_pod_agent(pod_id: str) -> Optional[Dict[str, Any]]:
    url = (
        f"{SUPABASE_URL}/rest/v1/agent_catalog"
        f"?id=eq.{quote(pod_id, safe='')}&is_active=eq.true&select=output_schema,system_prompt,tools"
        f"&limit=1"
    )
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, headers=_headers())
    if resp.status_code >= 400:
        raise RuntimeError(resp.text)
    rows = resp.json() or []
    return rows[0] if rows else None


async def fetch_approved_runs(
    *,
    limit: int = 1000,
    pod_id: str | None = None,
    run_id: str | None = None,
) -> List[Dict[str, Any]]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")

    base_select = (
        "select=id,created_at,pod_id,source_filename,raw_text,extracted_json,overall_confidence,status"
    )

    if run_id:
        rid = quote(str(run_id), safe="")
        query = f"{base_select}&id=eq.{rid}&limit=1"
    else:
        if not pod_id:
            raise RuntimeError("--pod-id is required when --run-id is not provided")
        pid = quote(str(pod_id), safe="")
        query = f"{base_select}&pod_id=eq.{pid}&status=eq.approved&limit={limit}&order=created_at.asc"

    url = f"{SUPABASE_URL}/rest/v1/pod_extraction_runs?{query}"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, headers=_headers())
    if resp.status_code >= 400:
        raise RuntimeError(resp.text)

    return resp.json() or []


def _default_instruction(pod_id: str) -> str:
    return (
        f"You are a structured extraction model for insurance pod '{pod_id}'. "
        f"Extract the required fields from the provided text. Return ONLY JSON and do not fabricate values."
    )


def _json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _flatten_json_paths(
    value: Any,
    *,
    prefix: str = "",
    max_items: int = 300,
) -> List[Tuple[str, Any]]:
    """
    Flatten JSON object/list into dot/bracket path-value pairs.
    Example path formats:
      - policy_info.policy_number
      - coverages[0].limit
    """
    out: List[Tuple[str, Any]] = []

    def _walk(v: Any, p: str) -> None:
        if len(out) >= max_items:
            return
        if isinstance(v, dict):
            for k, child in v.items():
                next_path = f"{p}.{k}" if p else str(k)
                _walk(child, next_path)
            return
        if isinstance(v, list):
            # Keep list expansion bounded so one large array does not dominate samples.
            for idx, child in enumerate(v[:25]):
                next_path = f"{p}[{idx}]" if p else f"[{idx}]"
                _walk(child, next_path)
            return
        out.append((p or "root", v))

    _walk(value, prefix)
    return out


def _build_base_instruction(
    *,
    pod_id: str,
    output_schema: Dict[str, Any],
    system_prompt: str,
    training_template: Optional[str],
) -> str:
    instruction = training_template or _default_instruction(pod_id)
    schema_str = json.dumps(output_schema, ensure_ascii=False, indent=2)
    if schema_str and schema_str.strip() and output_schema:
        instruction = (
            f"{instruction}\n\nOUTPUT_SCHEMA:\n{schema_str}\n\n"
            "Rules: return ONLY valid JSON matching the schema. "
            "Use null for missing/blank values. Include extra/unmodeled values under extra_fields."
        )
    elif system_prompt:
        instruction = f"{instruction}\n\nSYSTEM_PROMPT:\n{system_prompt}\n"
    return instruction


def _records_for_single_run(
    *,
    run: Dict[str, Any],
    pod_id: str,
    base_instruction: str,
    max_field_records: int = 80,
) -> List[Dict[str, Any]]:
    extracted = run.get("extracted_json") or {}
    raw_text = run.get("raw_text") or ""
    run_meta = {
        "run_id": run.get("id"),
        "source_filename": run.get("source_filename"),
        "overall_confidence": run.get("overall_confidence"),
    }
    domain = f"insurance/{pod_id}"
    records: List[Dict[str, Any]] = []

    # 1) Full-object extraction target (strict JSON).
    records.append(
        {
            "instruction": base_instruction,
            "input": raw_text,
            "output": _json_compact(extracted),
            "domain": domain,
            "metadata": {**run_meta, "sample_type": "full_object"},
        }
    )

    # 2) Top-level key extraction targets.
    if isinstance(extracted, dict):
        for key, value in extracted.items():
            records.append(
                {
                    "instruction": (
                        f"{base_instruction}\n\n"
                        f"Return ONLY this JSON key from the extraction result: '{key}'. "
                        f"Output must be a valid JSON object with exactly this key."
                    ),
                    "input": raw_text,
                    "output": _json_compact({key: value}),
                    "domain": domain,
                    "metadata": {**run_meta, "sample_type": "top_level_key", "json_path": key},
                }
            )

    # 3) Deep field-level targets (path-based supervision).
    flattened = _flatten_json_paths(extracted, max_items=max_field_records)
    for path, value in flattened:
        records.append(
            {
                "instruction": (
                    f"{base_instruction}\n\n"
                    f"Extract ONLY the value for JSON path '{path}'. "
                    "Return strictly valid JSON as: "
                    '{"path":"<path>","value":<json_value>} with no extra text.'
                ),
                "input": raw_text,
                "output": _json_compact({"path": path, "value": value}),
                "domain": domain,
                "metadata": {**run_meta, "sample_type": "field_path", "json_path": path},
            }
        )

    return records


def to_sft_records(
    *,
    runs: List[Dict[str, Any]],
    pod_id: str,
    agent: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    output_schema = (agent or {}).get("output_schema") or {}
    system_prompt = (agent or {}).get("system_prompt") or ""
    tools = (agent or {}).get("tools") or {}

    # Optional per-pod training instruction template stored in agent.tools.
    training_template = None
    if isinstance(tools, dict):
        training_template = tools.get("training_instruction_template")

    instruction = _build_base_instruction(
        pod_id=pod_id,
        output_schema=output_schema,
        system_prompt=system_prompt,
        training_template=training_template,
    )

    out: List[Dict[str, Any]] = []
    for r in runs:
        out.extend(
            _records_for_single_run(
                run=r,
                pod_id=pod_id,
                base_instruction=instruction,
            )
        )
    return out


def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export approved pod runs to JSONL")
    parser.add_argument("--out", default="fine_tuning/data/approved_pod.jsonl", help="Output JSONL path")
    parser.add_argument("--limit", type=int, default=1000, help="Max rows to export for batch mode")
    parser.add_argument("--run-id", default=None, help="Export a single run_id (must be approved)")
    parser.add_argument("--pod-id", default=None, help="Pod/agent id (agent_catalog.id)")
    args = parser.parse_args()

    async def _run() -> None:
        runs = await fetch_approved_runs(limit=args.limit, pod_id=args.pod_id, run_id=args.run_id)
        if not runs:
            print("No approved runs found; writing empty dataset.")
            out_path = Path(args.out).resolve()
            write_jsonl(out_path, [])
            return

        resolved_pod_id = args.pod_id or runs[0].get("pod_id")
        if not resolved_pod_id:
            raise RuntimeError("Could not resolve pod_id for dataset export")

        agent = await _fetch_one_pod_agent(str(resolved_pod_id))
        records = to_sft_records(runs=runs, pod_id=str(resolved_pod_id), agent=agent)
        out_path = Path(args.out).resolve()
        write_jsonl(out_path, records)
        print(f"Wrote {len(records)} records to {out_path}")

    import asyncio

    asyncio.run(_run())


if __name__ == "__main__":
    main()

