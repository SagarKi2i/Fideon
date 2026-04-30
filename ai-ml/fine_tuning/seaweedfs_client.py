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
_MULTIPART_CHUNK     = 256 * 1024 * 1024  # 256 MB chunks — fewer parts = fewer failure points


class SeaweedFSClient:
    def __init__(self) -> None:
        self._endpoint   = os.getenv("SEAWEEDFS_ENDPOINT", "").strip().rstrip("/")
        self._bucket     = os.getenv("SEAWEEDFS_BUCKET", "my-bucket").strip()
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
                read_timeout=1800,
                retries={"max_attempts": 5, "mode": "adaptive"},
            ),
        )

    def _transfer_config(self) -> Any:
        from boto3.s3.transfer import TransferConfig
        return TransferConfig(
            multipart_threshold=_MULTIPART_THRESHOLD,
            multipart_chunksize=_MULTIPART_CHUNK,
            max_concurrency=2,  # lower concurrency is more stable on SeaweedFS
        )

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
        tc = self._transfer_config()
        files = [f for f in local.rglob("*") if f.is_file()]
        print(f"[seaweedfs] Uploading HF model ({len(files)} files) → s3://{self._bucket}/{prefix}/")
        _RETRY_DELAYS = [30, 90]  # seconds to wait before attempt 2, 3
        failed: list[str] = []
        for f in files:
            rel = f.relative_to(local)
            key = f"{prefix}/{rel.as_posix()}"
            size_mb = f.stat().st_size // 1_000_000
            print(f"[seaweedfs]   {rel} ({size_mb} MB) …")
            last_exc: Exception | None = None
            for attempt in range(1, 4):  # 3 attempts per file
                try:
                    client.upload_file(str(f), self._bucket, key, Config=tc)
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < 3:
                        wait = _RETRY_DELAYS[attempt - 1]
                        print(f"[seaweedfs]   Retry {attempt}/3 for {rel} (waiting {wait}s): {exc}")
                        time.sleep(wait)
                    else:
                        print(f"[seaweedfs]   Retry {attempt}/3 for {rel}: {exc}")
            if last_exc is not None:
                failed.append(str(rel))
                print(f"[seaweedfs]   FAILED after 3 attempts: {rel} — {last_exc}")

        if failed:
            # Raise so training_orchestrator.promote_adapter() does not register this
            # version with an incomplete S3 path. The merged model is still on disk.
            raise RuntimeError(
                f"[seaweedfs] {len(failed)} file(s) failed to upload to {prefix} after 3 attempts. "
                f"SeaweedFS may be full or unhealthy. "
                f"Failed files: {', '.join(failed)}"
            )

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
        tc = self._transfer_config()
        files = list(local.glob("*.gguf")) + list(local.glob("manifest.json"))
        print(f"[seaweedfs] Uploading {len(files)} quantized file(s) → s3://{self._bucket}/{prefix}/")
        _RETRY_DELAYS = [30, 90]
        failed: list[str] = []
        for f in sorted(files):
            key = f"{prefix}/{f.name}"
            size_mb = f.stat().st_size // 1_000_000
            print(f"[seaweedfs]   {f.name} ({size_mb} MB) …")
            last_exc: Exception | None = None
            for attempt in range(1, 4):
                try:
                    client.upload_file(str(f), self._bucket, key, Config=tc)
                    last_exc = None
                    keys.append(key)
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < 3:
                        wait = _RETRY_DELAYS[attempt - 1]
                        print(f"[seaweedfs]   Retry {attempt}/3 for {f.name} (waiting {wait}s): {exc}")
                        time.sleep(wait)
                    else:
                        print(f"[seaweedfs]   Retry {attempt}/3 for {f.name}: {exc}")
            if last_exc is not None:
                failed.append(f.name)
                print(f"[seaweedfs]   FAILED after 3 attempts: {f.name} — {last_exc}")

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
        self._boto_client().upload_file(
            str(local_path), self._bucket, s3_key, Config=self._transfer_config()
        )
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
