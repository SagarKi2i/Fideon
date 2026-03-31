"""
Reject a bad approved ACORD extraction run so it is excluded from export.

Uses PostgREST with the service role (same as fine_tuning/export_approved_acord_dataset.py).
Table: acord_extraction_runs (not acord_form_summaries — that table is not used by export).

How to run (pick one):

  # A) From repo root — path to the script file (fine_tuning lives under backend/)
  python backend/fine_tuning/scripts/reject_bad_training_record.py

  # B) From backend/ — module form (cwd must be backend/ so `fine_tuning` is importable)
  cd backend
  python -m fine_tuning.scripts.reject_bad_training_record

If you see: ModuleNotFoundError: No module named 'fine_tuning'
  → You ran `python -m fine_tuning...` from the repo root. Use (A) or `cd backend` first.

Loads SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY via app.core.config (reads backend/.env when present).
"""
from __future__ import annotations

import os
import sys
from urllib.parse import quote

import httpx

# Ensure backend/ is importable when run as python -m fine_tuning.scripts.reject_bad_training_record
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.core.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL  # noqa: E402

TARGET_ID = "bbd1aa89-1d25-41df-ac8f-778e03551a70"
TARGET_FILE = "acord25_sample_demo.pdf"
REJECTION_REASON = (
    "Label leak: agency_name extracted as form label text 'License #:'. "
    "carrier and policy_number both null. "
    "Document appears to be a Certificate of Insurance, not an ACORD 125 application. "
    "Removed from training set to prevent corrupting fine-tuning labels."
)


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set. Run from backend/ with .env configured.")
        sys.exit(1)

    print(f"Looking up record: {TARGET_ID}")
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/acord_extraction_runs"
    qid = quote(TARGET_ID, safe="")
    with httpx.Client(timeout=60) as client:
        resp = client.get(
            f"{url}?select=id,source_filename,status&id=eq.{qid}&limit=1",
            headers=_headers(),
        )
    if resp.status_code >= 400:
        print(f"ERROR: GET failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    rows = resp.json()
    if not rows:
        print(f"ERROR: Record {TARGET_ID} not found in acord_extraction_runs")
        print("Check UUID and table name.")
        sys.exit(1)

    record = rows[0]
    print("Found record:")
    print(f"  id       : {record.get('id')}")
    print(f"  filename : {record.get('source_filename')}")
    print(f"  status   : {record.get('status')}")

    fn = record.get("source_filename") or ""
    if fn != TARGET_FILE:
        print("WARNING: filename mismatch!")
        print(f"  Expected : {TARGET_FILE}")
        print(f"  Found    : {fn}")
        if os.getenv("REJECT_BAD_RECORD_FORCE", "").strip().lower() not in {"1", "true", "yes"}:
            print("Set REJECT_BAD_RECORD_FORCE=1 to continue anyway, or fix TARGET_FILE.")
            sys.exit(1)

    if record.get("status") == "rejected":
        print("Record is already rejected. Nothing to do.")
        sys.exit(0)

    print(f"\nRejecting record {TARGET_ID}...")
    print(f"(Audit reason — not a DB column on acord_extraction_runs: {REJECTION_REASON})")

    patch_body = {"status": "rejected"}
    with httpx.Client(timeout=60) as client:
        upd = client.patch(
            f"{url}?id=eq.{qid}",
            headers=_headers(),
            json=patch_body,
        )
    if upd.status_code >= 400:
        print(f"ERROR: PATCH acord_extraction_runs failed: {upd.status_code} {upd.text}")
        sys.exit(1)
    updated_rows = upd.json() if upd.content else []
    if not updated_rows:
        print("ERROR: Update returned no rows. Check RLS or Prefer header.")
        sys.exit(1)

    updated = updated_rows[0]
    print("Successfully rejected:")
    print(f"  id     : {updated.get('id')}")
    print(f"  status : {updated.get('status')}")

    # Keep admin queue in sync when a row exists (state 'rejected' after sprint1 migration)
    with httpx.Client(timeout=60) as client:
        q = client.patch(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/acord_admin_queue?run_id=eq.{qid}",
            headers=_headers(),
            json={"state": "rejected", "reason": REJECTION_REASON[:2000]},
        )
    if q.status_code >= 400 and q.status_code != 404:
        print(f"NOTE: acord_admin_queue patch: {q.status_code} {q.text[:200]}")

    with httpx.Client(timeout=60) as client:
        verify = client.get(
            f"{url}?select=id,status&id=eq.{qid}&status=eq.approved&limit=1",
            headers=_headers(),
        )
    still = verify.json() if verify.status_code == 200 else []
    if still:
        print("ERROR: Record still shows as approved after update!")
        sys.exit(1)

    print("\nVerification PASSED — record will not appear in next export (status != approved).")
    print("Re-run: python -m fine_tuning.export_approved_acord_dataset ...")


if __name__ == "__main__":
    main()
