"""
Azure Blob Storage uploader — replaces seaweed_uploader.py.

Same UploadResult interface so call sites in job_runner and quantize_pipeline
are minimally changed.

Key layout (container = AZURE_BLOB_CONTAINER, default: fideon-models):
  adapters/{domain}/{version}/   — raw LoRA adapter files (HF format)
  gguf/{domain}/{version}/       — quantized GGUF artifacts
  finetuned/{version}/           — merged full-weight HF model (federated FL)
  finetuned/latest.txt           — plain-text latest promoted version number
  gradients/{model_id}/round-{N}/{device_id}/  — device FL submissions

Required env vars:
  AZURE_BLOB_ACCOUNT_URL   e.g. https://swtier.blob.core.windows.net
  AZURE_BLOB_SAS_TOKEN     SAS token (without leading '?')
  AZURE_BLOB_CONTAINER     container name (default: fideon-models)
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import NamedTuple


class UploadResult(NamedTuple):
    prefix: str
    files: list[dict]
    domain: str
    version: str
    total_bytes: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _container_client(*, create_if_missing: bool = False):
    from azure.storage.blob import BlobServiceClient
    account_url = os.getenv("AZURE_BLOB_ACCOUNT_URL", "").strip().rstrip("/")
    sas_token   = os.getenv("AZURE_BLOB_SAS_TOKEN",   "").strip().lstrip("?")
    container   = os.getenv("AZURE_BLOB_CONTAINER", "fideon-models").strip()
    if not (account_url and sas_token):
        raise RuntimeError(
            "Azure Blob not configured — "
            "set AZURE_BLOB_ACCOUNT_URL and AZURE_BLOB_SAS_TOKEN"
        )
    svc = BlobServiceClient(account_url=f"{account_url}?{sas_token}")
    cc  = svc.get_container_client(container)
    if create_if_missing:
        try:
            cc.create_container()
        except Exception:
            pass
    return cc


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_RETRY_DELAYS = [15, 30, 60, 120]


def _upload_file(cc, blob_name: str, file_path: Path, *, log_fn=None) -> None:
    size = file_path.stat().st_size
    last_exc: Exception | None = None
    for attempt in range(1, 5):
        try:
            with open(file_path, "rb") as fh:
                cc.get_blob_client(blob_name).upload_blob(
                    fh, overwrite=True, max_concurrency=4, length=size
                )
            return
        except Exception as exc:
            last_exc = exc
            wait = _RETRY_DELAYS[min(attempt - 1, len(_RETRY_DELAYS) - 1)]
            if log_fn:
                log_fn(f"[azure] retry {attempt}/4 for {blob_name} in {wait}s: {exc}\n")
            time.sleep(wait)
    raise RuntimeError(f"Upload failed after 4 attempts: {blob_name} — {last_exc}")


# ---------------------------------------------------------------------------
# Public upload helpers
# ---------------------------------------------------------------------------

def upload_adapter_weights(
    output_dir: Path,
    domain: str,
    version_name: str,
    *,
    log_fn=None,
) -> UploadResult:
    """Upload every file under output_dir to adapters/{domain}/{version_name}/."""
    prefix = f"adapters/{domain}/{version_name}"
    cc = _container_client(create_if_missing=True)
    uploaded: list[dict] = []
    total_bytes = 0

    for file_path in sorted(output_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(output_dir).as_posix()
        blob_name = f"{prefix}/{rel}"
        size = file_path.stat().st_size
        sha  = _sha256_file(file_path)
        if log_fn:
            log_fn(f"[azure] upload {rel} ({size:,} bytes) -> {blob_name}\n")
        _upload_file(cc, blob_name, file_path, log_fn=log_fn)
        uploaded.append({"key": blob_name, "name": rel, "sha256": sha, "size_bytes": size})
        total_bytes += size

    if log_fn:
        log_fn(
            f"[azure] adapter upload complete: {len(uploaded)} files, "
            f"{total_bytes:,} bytes, prefix={prefix}\n"
        )
    return UploadResult(
        prefix=prefix,
        files=uploaded,
        domain=domain,
        version=version_name,
        total_bytes=total_bytes,
    )


def upload_directory(
    local_dir: Path,
    prefix: str,
    *,
    log_fn=None,
) -> list[dict]:
    """Upload every file under local_dir to the given Azure Blob prefix."""
    cc = _container_client(create_if_missing=True)
    uploaded: list[dict] = []

    for fp in sorted(local_dir.rglob("*")):
        if not fp.is_file():
            continue
        rel = fp.relative_to(local_dir).as_posix()
        blob_name = f"{prefix}/{rel}"
        size  = fp.stat().st_size
        sha256 = _sha256_file(fp)
        if log_fn:
            log_fn(f"[azure] {rel} ({size:,} bytes) -> {blob_name}\n")
        _upload_file(cc, blob_name, fp, log_fn=log_fn)
        uploaded.append({"key": blob_name, "name": rel, "sha256": sha256, "size_bytes": size})

    if log_fn:
        total = sum(f["size_bytes"] for f in uploaded)
        log_fn(f"[azure] uploaded {len(uploaded)} file(s), {total:,} bytes -> {prefix}/\n")
    return uploaded


def upload_gguf_artifacts(
    gguf_dir: Path,
    domain: str,
    version_name: str,
    *,
    log_fn=None,
) -> list[dict]:
    """Upload *.gguf files (excluding fp16) to gguf/{domain}/{version_name}/."""
    prefix = f"gguf/{domain}/{version_name}"
    cc = _container_client(create_if_missing=True)
    artifacts: list[dict] = []

    for gguf_path in sorted(gguf_dir.glob("*.gguf")):
        if "fp16" in gguf_path.name.lower():
            continue
        quant_level = _parse_quant_level(gguf_path.name)
        blob_name   = f"{prefix}/{gguf_path.name}"
        sha  = _sha256_file(gguf_path)
        size = gguf_path.stat().st_size
        if log_fn:
            log_fn(
                f"[azure] upload GGUF {gguf_path.name} "
                f"({size:,} bytes, quant={quant_level}) -> {blob_name}\n"
            )
        _upload_file(cc, blob_name, gguf_path, log_fn=log_fn)
        artifacts.append({
            "blob_key":        blob_name,
            "quant_level":     quant_level,
            "sha256":          sha,
            "size_bytes":      size,
            "domain":          domain,
            "adapter_version": version_name,
        })

    return artifacts


# ---------------------------------------------------------------------------
# Download helper (used by federated aggregator)
# ---------------------------------------------------------------------------

def download_adapter(
    prefix: str,
    local_dir: Path,
    *,
    log_fn=None,
) -> list[Path]:
    """Download all blobs under prefix into local_dir. Returns list of local paths."""
    cc = _container_client()
    local_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    clean_prefix = prefix.rstrip("/") + "/"

    for blob_props in cc.list_blobs(name_starts_with=clean_prefix):
        blob_name: str = blob_props["name"]
        rel = blob_name[len(clean_prefix):]
        if not rel:
            continue
        dest = local_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if log_fn:
            log_fn(f"[azure] download {blob_name} -> {dest}\n")
        downloader = cc.get_blob_client(blob_name).download_blob(max_concurrency=4)
        with open(dest, "wb") as fh:
            for chunk in downloader.chunks():
                fh.write(chunk)
        downloaded.append(dest)

    return downloaded


# ---------------------------------------------------------------------------
# Version pointer (latest.txt) — used by federated aggregator
# ---------------------------------------------------------------------------

def get_latest_version() -> int:
    """Read finetuned/latest.txt. Returns int version number, 0 if absent."""
    try:
        cc = _container_client()
        data = cc.get_blob_client("finetuned/latest.txt").download_blob(timeout=10).readall()
        raw = data.decode().strip()
        return int(raw) if raw.isdigit() else 0
    except Exception:
        return 0


def write_latest_version(version_int: int) -> None:
    """Write version_int to finetuned/latest.txt."""
    cc = _container_client(create_if_missing=True)
    cc.get_blob_client("finetuned/latest.txt").upload_blob(
        str(version_int).encode(), overwrite=True
    )


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _parse_quant_level(filename: str) -> str:
    lower = filename.lower()
    for level in [
        "q8_0", "q6_k", "q5_k_m", "q5_k_s",
        "q4_k_m", "q4_k_s", "q4_0",
        "q3_k_m", "q3_k_s", "q2_k",
        "f16", "f32",
    ]:
        if level in lower:
            return level
    return "unknown"
