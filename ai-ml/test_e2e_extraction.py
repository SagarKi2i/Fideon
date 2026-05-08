#!/usr/bin/env python3
"""
E2E Extraction Test — Fideon RunPod
====================================
Tests the full upload → extract pipeline against a live RunPod pod for both
Digital and Scanned PDFs.

Usage
-----
  # Minimal: provide the pod URL and one or two PDFs
  python test_e2e_extraction.py --url http://<pod-ip>:8080 \
      --digital path/to/digital.pdf \
      --scanned path/to/scanned.pdf

  # Run with only digital or only scanned (the other is skipped):
  python test_e2e_extraction.py --url http://<pod-ip>:8080 --digital myform.pdf

  # Override ACORD form type (default: 25):
  python test_e2e_extraction.py --url ... --digital d.pdf --form-type 130

  # Skip the upload step if you already have an upload_id:
  python test_e2e_extraction.py --url ... --upload-id abc-123 --label digital

Environment variables (alternative to CLI flags):
  RUNPOD_URL      — pod base URL (e.g. https://abc123-8080.proxy.runpod.net)
  RUNPOD_API_KEY  — RunPod API key if the pod is behind RunPod's proxy gateway
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------
try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' not installed. Run:  pip install requests")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

_NO_COLOR = not sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return text if _NO_COLOR else f"{code}{text}{RESET}"


def _header(msg: str) -> None:
    bar = "─" * 60
    print(f"\n{_c(BOLD + CYAN, bar)}")
    print(f"{_c(BOLD + CYAN, msg)}")
    print(_c(BOLD + CYAN, bar))


def _ok(msg: str) -> None:
    print(f"  {_c(GREEN, '✓')} {msg}")


def _warn(msg: str) -> None:
    print(f"  {_c(YELLOW, '!')} {msg}")


def _err(msg: str) -> None:
    print(f"  {_c(RED, '✗')} {msg}")


def _step(msg: str) -> None:
    print(f"  → {msg}")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

class PodClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 360) -> None:
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def get(self, path: str, **kw) -> requests.Response:
        return self.session.get(f"{self.base}{path}", timeout=self.timeout, **kw)

    def post(self, path: str, **kw) -> requests.Response:
        return self.session.post(f"{self.base}{path}", timeout=self.timeout, **kw)


# ---------------------------------------------------------------------------
# Test steps
# ---------------------------------------------------------------------------

def check_health(client: PodClient) -> bool:
    _header("STEP 1 — Health Check")
    try:
        r = client.get("/health")
        r.raise_for_status()
        body = r.json()
        _ok(f"Pod is healthy: {json.dumps(body)}")
        return True
    except Exception as exc:
        _err(f"Health check failed: {exc}")
        return False


def upload_pdf(client: PodClient, pdf_path: str, form_type: str) -> Optional[str]:
    path = Path(pdf_path)
    if not path.exists():
        _err(f"PDF not found: {pdf_path}")
        return None

    size_mb = path.stat().st_size / 1_000_000
    _step(f"Uploading {path.name} ({size_mb:.2f} MB) …")

    t0 = time.monotonic()
    try:
        with open(path, "rb") as fh:
            r = client.post(
                f"/upload?form_type={form_type}",
                files={"file": (path.name, fh, "application/pdf")},
            )
        r.raise_for_status()
        record = r.json()
        elapsed = time.monotonic() - t0
        upload_id = record["upload_id"]
        _ok(f"Uploaded in {elapsed:.1f}s — upload_id: {upload_id}")
        return upload_id
    except Exception as exc:
        _err(f"Upload failed: {exc}")
        if hasattr(exc, "response") and exc.response is not None:
            _err(f"Response body: {exc.response.text[:500]}")
        return None


def run_extraction(
    client: PodClient,
    upload_id: str,
    form_type: str,
    label: str,
    output_dir: Path,
) -> Optional[Dict[str, Any]]:
    _step(f"Running full extraction (Surya OCR + Docling + Qwen VL) — this can take 1–5 min …")

    t0 = time.monotonic()
    try:
        r = client.post(
            f"/extract/{upload_id}?form_type_hint={form_type}",
        )
        r.raise_for_status()
        result: Dict[str, Any] = r.json()
        elapsed = time.monotonic() - t0
        _ok(f"Extraction completed in {elapsed:.1f}s")
    except Exception as exc:
        elapsed = time.monotonic() - t0
        _err(f"Extraction failed after {elapsed:.1f}s: {exc}")
        if hasattr(exc, "response") and exc.response is not None:
            _err(f"Response body: {exc.response.text[:500]}")
        return None

    # Save to file
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_file = output_dir / f"result_{label}_{ts}.json"
    out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    _ok(f"Full result saved → {out_file}")

    return result


def print_extraction_summary(result: Dict[str, Any], label: str) -> bool:
    """Print a human-readable summary and return True if extraction looks successful."""
    _header(f"RESULT SUMMARY — {label.upper()}")

    pdf_type      = result.get("pdf_type", "unknown")
    form_detected = result.get("form_type_detected", result.get("form_type", "?"))
    full_text     = result.get("full_text") or result.get("raw_text") or ""
    markdown      = result.get("markdown", "")
    warnings      = result.get("warnings", [])

    # Field extraction — server may return under different keys
    fields: Dict[str, Any] = (
        result.get("extracted_json")
        or result.get("extracted_fields")
        or result.get("fields")
        or {}
    )

    print(f"  PDF type detected : {_c(BOLD, pdf_type)}")
    print(f"  Form type         : {_c(BOLD, str(form_detected))}")
    print(f"  Full-text length  : {len(full_text)} chars")
    print(f"  Markdown length   : {len(markdown)} chars")
    print(f"  Fields extracted  : {len(fields)}")

    # Key ACORD-25 fields of interest
    KEY_FIELDS = [
        "agency_name", "agency", "carrier", "insurer_name",
        "policy_number", "policy_no", "named_insured", "insured_name",
        "effective_date", "expiration_date", "gl_each_occurrence",
        "contact_name", "phone",
    ]
    found_keys = {k.lower(): k for k in fields}
    print(f"\n  {'Field':<30} {'Value':<50}")
    print(f"  {'─'*30} {'─'*50}")
    printed = 0
    for kf in KEY_FIELDS:
        for fk, orig_key in found_keys.items():
            if kf in fk:
                raw_val = fields[orig_key]
                if isinstance(raw_val, dict):
                    val = raw_val.get("value", raw_val)
                else:
                    val = raw_val
                val_str = str(val)[:48] if val not in (None, "", "N/A") else _c(YELLOW, "(empty)")
                print(f"  {orig_key:<30} {val_str}")
                printed += 1
                break

    if printed == 0:
        _warn("No key fields matched — printing first 10 fields:")
        for i, (k, v) in enumerate(list(fields.items())[:10]):
            val_str = str(v)[:48] if v not in (None, "", "N/A") else _c(YELLOW, "(empty)")
            print(f"  {k:<30} {val_str}")

    if warnings:
        print()
        for w in warnings:
            _warn(f"Warning: {w}")

    # Pass/fail heuristic
    has_text   = len(full_text) > 50 or len(markdown) > 50
    has_fields = len(fields) > 0
    passed     = has_text and has_fields

    print()
    if passed:
        print(f"  {_c(BOLD + GREEN, 'PASS')} — text extracted and fields populated")
    else:
        print(f"  {_c(BOLD + RED, 'FAIL')} — " + (
            "no text extracted" if not has_text else "no fields extracted"
        ))

    return passed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="E2E extraction test against a Fideon RunPod pod",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage")[0].strip(),
    )
    p.add_argument("--url", default=os.getenv("RUNPOD_URL", ""),
                   help="Pod base URL, e.g. http://localhost:8080 (or set RUNPOD_URL)")
    p.add_argument("--api-key", default=os.getenv("RUNPOD_API_KEY", ""),
                   help="RunPod proxy API key (optional)")
    p.add_argument("--digital", metavar="PDF", default="",
                   help="Path to a digital (text-layer) PDF")
    p.add_argument("--scanned", metavar="PDF", default="",
                   help="Path to a scanned (image-only) PDF")
    p.add_argument("--form-type", default="25",
                   help="ACORD form type hint (default: 25)")
    p.add_argument("--timeout", type=int, default=360,
                   help="HTTP timeout in seconds for the extract call (default: 360)")
    p.add_argument("--upload-id", default="",
                   help="Skip upload and use an existing upload_id (requires --label)")
    p.add_argument("--label", default="digital",
                   choices=["digital", "scanned"],
                   help="Label for --upload-id mode (default: digital)")
    p.add_argument("--output-dir", default=".",
                   help="Directory to save result JSON files (default: current dir)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not args.url:
        print("ERROR: --url is required (or set RUNPOD_URL env var)")
        print("Example: python test_e2e_extraction.py --url http://localhost:8080 --digital form.pdf")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = PodClient(args.url, api_key=args.api_key or None, timeout=args.timeout)

    print(f"\n{_c(BOLD, 'Fideon RunPod E2E Extraction Test')}")
    print(f"Pod URL   : {args.url}")
    print(f"Form type : ACORD {args.form_type}")
    print(f"Output dir: {output_dir.resolve()}")

    # ── Health ────────────────────────────────────────────────────────────────
    if not check_health(client):
        print(_c(RED, "\nAborting: pod is unreachable."))
        return 1

    results: Dict[str, bool] = {}

    # ── Build test cases ──────────────────────────────────────────────────────
    test_cases: list[tuple[str, str, str]] = []  # (label, pdf_path, upload_id)

    if args.upload_id:
        # Direct upload_id mode — skip upload
        test_cases.append((args.label, "", args.upload_id))
    else:
        if args.digital:
            test_cases.append(("digital", args.digital, ""))
        if args.scanned:
            test_cases.append(("scanned", args.scanned, ""))
        if not test_cases:
            print(_c(YELLOW, "\nNo PDFs provided. Use --digital or --scanned to specify test files."))
            print("Example:  python test_e2e_extraction.py --url http://localhost:8080 --digital form.pdf")
            return 0

    # ── Run each test case ────────────────────────────────────────────────────
    for label, pdf_path, upload_id in test_cases:
        _header(f"TEST CASE — {label.upper()} PDF")

        if pdf_path:
            _step(f"PDF: {pdf_path}")
            _header(f"STEP 2 — Upload ({label})")
            upload_id = upload_id or upload_pdf(client, pdf_path, args.form_type)
            if not upload_id:
                results[label] = False
                continue
        else:
            _ok(f"Using existing upload_id: {upload_id}")

        _header(f"STEP 3 — Extract ({label})")
        result = run_extraction(client, upload_id, args.form_type, label, output_dir)
        if result is None:
            results[label] = False
            continue

        results[label] = print_extraction_summary(result, label)

    # ── Final report ──────────────────────────────────────────────────────────
    _header("FINAL REPORT")
    all_pass = True
    for label, passed in results.items():
        status = _c(BOLD + GREEN, "PASS") if passed else _c(BOLD + RED, "FAIL")
        print(f"  {label:<10} {status}")
        if not passed:
            all_pass = False

    if not results:
        print("  (no tests ran)")
        return 0

    print()
    if all_pass:
        print(_c(BOLD + GREEN, "All tests PASSED"))
        return 0
    else:
        print(_c(BOLD + RED, "One or more tests FAILED"))
        return 1


if __name__ == "__main__":
    sys.exit(main())
