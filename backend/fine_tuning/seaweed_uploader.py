"""
Upload and download fine-tuned adapter weights and GGUF artifacts via SeaweedFS (S3-compatible).

Key layout inside the bucket:
  adapters/{domain}/{version}/  — raw LoRA adapter files (HF format)
  gguf/{domain}/{version}/      — quantized GGUF artifacts
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import NamedTuple

import boto3
from botocore.config import Config


class UploadResult(NamedTuple):
    prefix: str
    files: list[dict]
    domain: str
    version: str
    total_bytes: int


def _s3_client():
    endpoint = os.getenv("SEAWEEDFS_ENDPOINT", "").strip()
    access_key = os.getenv("SEAWEEDFS_ACCESS_KEY", "").strip()
    secret_key = os.getenv("SEAWEEDFS_SECRET_KEY", "").strip()
    if not all([endpoint, access_key, secret_key]):
        raise RuntimeError(
            "SeaweedFS not configured — set SEAWEEDFS_ENDPOINT, "
            "SEAWEEDFS_ACCESS_KEY, SEAWEEDFS_SECRET_KEY."
        )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )


def _bucket() -> str:
    b = os.getenv("SEAWEEDFS_BUCKET", "").strip()
    if not b:
        raise RuntimeError("SEAWEEDFS_BUCKET not configured.")
    return b


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_adapter_weights(
    output_dir: Path,
    domain: str,
    version_name: str,
    *,
    log_fn=None,
) -> UploadResult:
    """
    Upload every file under output_dir to SeaweedFS at
    adapters/{domain}/{version_name}/.

    Returns an UploadResult with the S3 prefix and per-file metadata.
    """
    bucket = _bucket()
    s3 = _s3_client()
    prefix = f"adapters/{domain}/{version_name}"
    uploaded: list[dict] = []
    total_bytes = 0

    for file_path in sorted(output_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(output_dir).as_posix()
        key = f"{prefix}/{rel}"
        size = file_path.stat().st_size
        sha = _sha256_file(file_path)
        if log_fn:
            log_fn(f"[seaweed] upload {rel} ({size:,} bytes) -> s3://{bucket}/{key}\n")
        s3.upload_file(str(file_path), bucket, key)
        uploaded.append({"key": key, "name": rel, "sha256": sha, "size_bytes": size})
        total_bytes += size

    if log_fn:
        log_fn(
            f"[seaweed] adapter upload complete: {len(uploaded)} files, "
            f"{total_bytes:,} bytes total, prefix={prefix}\n"
        )
    return UploadResult(
        prefix=prefix,
        files=uploaded,
        domain=domain,
        version=version_name,
        total_bytes=total_bytes,
    )


def download_from_seaweedfs(
    prefix: str,
    local_dir: Path,
    *,
    log_fn=None,
) -> list[Path]:
    """
    Download all objects under prefix to local_dir, preserving relative paths.
    Returns list of downloaded local paths.
    """
    bucket = _bucket()
    s3 = _s3_client()
    local_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            key: str = obj["Key"]
            rel = key[len(prefix):].lstrip("/")
            if not rel:
                continue
            dest = local_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if log_fn:
                log_fn(f"[seaweed] download s3://{bucket}/{key} -> {dest}\n")
            s3.download_file(bucket, key, str(dest))
            downloaded.append(dest)

    return downloaded


def upload_gguf_artifacts(
    gguf_dir: Path,
    domain: str,
    version_name: str,
    *,
    log_fn=None,
) -> list[dict]:
    """
    Upload all *.gguf files in gguf_dir to gguf/{domain}/{version_name}/ in SeaweedFS.
    Returns a list of artifact dicts ready for adapter_registry insertion.
    """
    bucket = _bucket()
    s3 = _s3_client()
    artifacts: list[dict] = []

    for gguf_path in sorted(gguf_dir.glob("*.gguf")):
        quant_level = _parse_quant_level(gguf_path.name)
        key = f"gguf/{domain}/{version_name}/{gguf_path.name}"
        sha = _sha256_file(gguf_path)
        size = gguf_path.stat().st_size
        if log_fn:
            log_fn(
                f"[seaweed] upload GGUF {gguf_path.name} "
                f"({size:,} bytes, quant={quant_level}) -> s3://{bucket}/{key}\n"
            )
        s3.upload_file(str(gguf_path), bucket, key)
        artifacts.append(
            {
                "blob_key": key,
                "quant_level": quant_level,
                "sha256": sha,
                "size_bytes": size,
                "domain": domain,
                "adapter_version": version_name,
            }
        )

    return artifacts


def _parse_quant_level(filename: str) -> str:
    """Extract quant level tag from GGUF filename (e.g. 'model-Q4_K_M.gguf' -> 'q4_k_m')."""
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
