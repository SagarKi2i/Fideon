"""
SeaweedFS (S3-compatible) client.

Bucket layout:
  finetuned/v{N}/      — merged full-weight HF model (safetensors + config)
  finetuned/latest.txt — plain text: latest promoted version number
  quantized/v{N}/      — GGUF quantized files + manifest.json

Required env vars (all optional — if SEAWEEDFS_ENDPOINT is unset, uploads are no-ops):
  SEAWEEDFS_ENDPOINT   — e.g. http://seaweedfs-gateway:8333
  SEAWEEDFS_BUCKET     — bucket name (default: fideon-adapters)
  SEAWEEDFS_ACCESS_KEY — S3 access key
  SEAWEEDFS_SECRET_KEY — S3 secret key
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_MULTIPART_THRESHOLD = 64 * 1024 * 1024    # 64 MB
_MULTIPART_CHUNK     = 256 * 1024 * 1024  # 256 MB chunks — fewer parts, less SeaweedFS pressure
_GGUF_SIZE_THRESHOLD = 1 * 1024 * 1024 * 1024  # files > 1 GB get conservative settings
_UPLOAD_MAX_RETRIES  = 5                   # file-level retries (on top of botocore request retries)


class SeaweedFSClient:
    def __init__(self) -> None:
        self._endpoint   = os.getenv("SEAWEEDFS_ENDPOINT", "").strip().rstrip("/")
        self._bucket     = os.getenv("SEAWEEDFS_BUCKET", "fideon-adapters").strip()
        self._access_key = os.getenv("SEAWEEDFS_ACCESS_KEY", "").strip()
        self._secret_key = os.getenv("SEAWEEDFS_SECRET_KEY", "").strip()

    @property
    def _configured(self) -> bool:
        return bool(self._endpoint)

    def _boto_client(self) -> Any:
        import boto3
        from botocore.config import Config
        return boto3.client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            config=Config(
                signature_version="s3v4",
                connect_timeout=60,
                read_timeout=1800,  # 30 min — large GGUF files need more time
                retries={"max_attempts": 5, "mode": "adaptive"},
            ),
        )

    def _transfer_config(self, file_size_bytes: int = 0) -> Any:
        from boto3.s3.transfer import TransferConfig
        # Large files (>1 GB): sequential upload, big chunks — avoids SeaweedFS 500 errors
        # under concurrent multipart pressure
        if file_size_bytes > _GGUF_SIZE_THRESHOLD:
            return TransferConfig(
                multipart_threshold=_MULTIPART_THRESHOLD,
                multipart_chunksize=_MULTIPART_CHUNK,
                max_concurrency=1,  # sequential — most reliable for large files on SeaweedFS
            )
        return TransferConfig(
            multipart_threshold=_MULTIPART_THRESHOLD,
            multipart_chunksize=_MULTIPART_CHUNK,
            max_concurrency=2,  # lower concurrency is more stable on SeaweedFS
        )

    def _upload_file_with_retry(self, client: Any, local_path: str, key: str) -> None:
        """Upload a single file with file-level retries on top of botocore retries."""
        import time
        size = Path(local_path).stat().st_size
        tc = self._transfer_config(size)
        last_exc: Exception = RuntimeError("upload never attempted")
        for attempt in range(1, _UPLOAD_MAX_RETRIES + 1):
            try:
                client.upload_file(local_path, self._bucket, key, Config=tc)
                return
            except Exception as exc:
                last_exc = exc
                if attempt < _UPLOAD_MAX_RETRIES:
                    wait = 10 * attempt  # 10s, 20s, 30s, 40s back-off
                    print(f"[seaweedfs]   upload failed (attempt {attempt}/{_UPLOAD_MAX_RETRIES}): {exc} — retrying in {wait}s …")
                    time.sleep(wait)
        raise RuntimeError(f"Upload failed after {_UPLOAD_MAX_RETRIES} attempts: {last_exc}") from last_exc

    # ── Fine-tuned model (full HF weights) ───────────────────────────────────

    def upload_hf_model(self, local_dir: str, version: int) -> str:
        """
        Upload entire merged HF model directory to finetuned/v{version}/.
        Also writes finetuned/latest.txt so the next training cycle can find it.
        Returns the S3 prefix used.
        """
        prefix = f"finetuned/v{version}"
        if not self._configured:
            print(f"[seaweedfs] Not configured — skipping HF model upload (prefix: {prefix}/)")
            return prefix

        local = Path(local_dir)
        client = self._boto_client()
        files = [f for f in local.rglob("*") if f.is_file()]
        print(f"[seaweedfs] Uploading HF model ({len(files)} files) → s3://{self._bucket}/{prefix}/")
        _RETRY_DELAYS = [30, 90]  # seconds to wait before attempt 2, 3
        failed: list[str] = []
        for f in files:
            rel = f.relative_to(local)
            key = f"{prefix}/{rel.as_posix()}"
            size_mb = f.stat().st_size // 1_000_000
            print(f"[seaweedfs]   {rel} ({size_mb} MB) …")
            self._upload_file_with_retry(client, str(f), key)

        if failed:
            # Training succeeded — don't mark job as failed just because SeaweedFS is down.
            # The merged model is still on disk; next cycle will re-upload.
            # Do NOT write latest.txt — an incomplete upload must not be used as base model.
            print(
                f"[seaweedfs] WARNING: {len(failed)} file(s) failed to upload to {prefix}. "
                f"Model is preserved on disk. SeaweedFS may be full or unhealthy. "
                f"Failed files: {', '.join(failed)}"
            )
            return prefix

        # Only mark as latest when ALL files uploaded successfully
        client.put_object(
            Bucket=self._bucket,
            Key="finetuned/latest.txt",
            Body=str(version).encode(),
        )
        print(f"[seaweedfs] HF model uploaded. Latest → v{version}")
        return prefix

    def get_latest_finetuned_version(self) -> Optional[int]:
        """Return the latest fine-tuned version number from SeaweedFS, or None."""
        if not self._configured:
            return None
        try:
            client = self._boto_client()
            resp = client.get_object(Bucket=self._bucket, Key="finetuned/latest.txt")
            return int(resp["Body"].read().decode().strip())
        except Exception:
            return None

    def download_finetuned_model(self, version: int, local_dir: str) -> str:
        """
        Download fine-tuned HF model from finetuned/v{version}/ to local_dir.
        Returns local_dir.
        """
        if not self._configured:
            raise RuntimeError("SEAWEEDFS_ENDPOINT not configured — cannot download model")

        prefix = f"finetuned/v{version}/"
        local = Path(local_dir)
        local.mkdir(parents=True, exist_ok=True)
        client = self._boto_client()
        tc = self._transfer_config()

        paginator = client.get_paginator("list_objects_v2")
        total = 0
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel = key[len(prefix):]
                if not rel:
                    continue
                dest = local / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                size_mb = obj.get("Size", 0) // 1_000_000
                print(f"[seaweedfs] Downloading {rel} ({size_mb} MB) …")
                client.download_file(self._bucket, key, str(dest), Config=tc)
                total += 1

        print(f"[seaweedfs] Downloaded {total} files → {local_dir}")
        return local_dir

    # ── Quantized GGUF ────────────────────────────────────────────────────────

    def upload_quantized(self, gguf_dir: str, version: int) -> List[str]:
        """
        Upload all .gguf files and manifest.json from gguf_dir to
        quantized/v{version}/.
        Returns list of S3 keys uploaded.
        """
        prefix = f"quantized/v{version}"
        local = Path(gguf_dir)
        keys: List[str] = []

        if not self._configured:
            print(f"[seaweedfs] Not configured — skipping quantized upload (prefix: {prefix}/)")
            return keys

        client = self._boto_client()
        # Exclude fp16.gguf — it's a 16 GB intermediate file, not needed for inference
        files = [f for f in local.glob("*.gguf") if "fp16" not in f.name] + list(local.glob("manifest.json"))
        print(f"[seaweedfs] Uploading {len(files)} quantized file(s) → s3://{self._bucket}/{prefix}/")
        _RETRY_DELAYS = [30, 90]
        failed: list[str] = []
        for f in sorted(files):
            key = f"{prefix}/{f.name}"
            size_mb = f.stat().st_size // 1_000_000
            print(f"[seaweedfs]   {f.name} ({size_mb} MB) …")
            self._upload_file_with_retry(client, str(f), key)
            keys.append(key)

        if failed:
            print(f"[seaweedfs] WARNING: {len(failed)} GGUF file(s) failed to upload: {', '.join(failed)}")
        else:
            print(f"[seaweedfs] Quantized upload complete ({len(keys)} files).")
        return keys

    # ── Legacy helpers ────────────────────────────────────────────────────────

    def upload_gguf(self, local_path: Path, adapter_id: str, version: str) -> str:
        """Upload a single GGUF file to adapters/{adapter_id}/{version}/. Returns S3 key."""
        s3_key = f"adapters/{adapter_id}/{version}/{local_path.name}"
        if not self._configured:
            print(f"[seaweedfs] Not configured — skipping GGUF upload ({local_path.name})")
            return s3_key
        print(f"[seaweedfs] Uploading {local_path} → s3://{self._bucket}/{s3_key} …")
        self._upload_file_with_retry(self._boto_client(), str(local_path), s3_key)
        return s3_key

    def get_sha256(self, s3_key: str) -> Optional[str]:
        if not self._configured:
            return None
        try:
            import io
            buf = io.BytesIO()
            self._boto_client().download_fileobj(self._bucket, s3_key, buf)
            buf.seek(0)
            return hashlib.sha256(buf.read()).hexdigest()
        except Exception as exc:
            print(f"[seaweedfs] SHA-256 check failed: {exc}")
            return None

    def find_gguf(self, adapter_path: str) -> Optional[Path]:
        """Return the first .gguf file found in adapter_path, or None."""
        p = Path(adapter_path)
        gguf_files = list(p.glob("*.gguf"))
        return gguf_files[0] if gguf_files else None
