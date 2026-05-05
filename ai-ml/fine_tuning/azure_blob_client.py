"""
Azure Blob Storage client — drop-in replacement for SeaweedFSClient.

Bucket layout (same as SeaweedFS):
  finetuned/v{N}/      — merged full-weight HF model (safetensors + config)
  finetuned/latest.txt — plain text: latest promoted version number
  quantized/v{N}/      — GGUF quantized files + manifest.json

Required env vars (all optional — if AZURE_BLOB_ACCOUNT_URL is unset, uploads are no-ops):
  AZURE_BLOB_ACCOUNT_URL  — e.g. https://swtier.blob.core.windows.net
  AZURE_BLOB_SAS_TOKEN    — SAS token (without leading '?')
  AZURE_BLOB_CONTAINER    — container name (default: fideon-models)
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any, Callable, List, Optional

_CHUNK_SIZE = 256 * 1024 * 1024  # 256 MB upload chunks


class AzureBlobClient:
    def __init__(self) -> None:
        self._account_url = os.getenv("AZURE_BLOB_ACCOUNT_URL", "").strip().rstrip("/")
        self._sas_token   = os.getenv("AZURE_BLOB_SAS_TOKEN", "").strip().lstrip("?")
        self._container   = os.getenv("AZURE_BLOB_CONTAINER", "fideon-models").strip()

    @property
    def _configured(self) -> bool:
        return bool(self._account_url and self._sas_token)

    # surface these so callers that read ._endpoint / ._bucket still work
    @property
    def _endpoint(self) -> str:
        return self._account_url

    @property
    def _bucket(self) -> str:
        return self._container

    def _service_client(self) -> Any:
        from azure.storage.blob import BlobServiceClient
        url = f"{self._account_url}?{self._sas_token}"
        return BlobServiceClient(account_url=url)

    def _container_client(self, create_if_missing: bool = False) -> Any:
        cc = self._service_client().get_container_client(self._container)
        if create_if_missing:
            try:
                cc.create_container()
                print(f"[azure_blob] Created container: {self._container}")
            except Exception:
                pass  # already exists — ignore
        return cc

    # ── probe (used by pre-flight check) ─────────────────────────────────────

    def probe(self) -> None:
        """Raise if the container is unreachable."""
        cc = self._container_client()
        # list_blobs with max_results=1 is the lightest possible check
        next(iter(cc.list_blobs(name_starts_with="finetuned/", results_per_page=1)), None)

    # ── Fine-tuned model (full HF weights) ───────────────────────────────────

    def upload_hf_model(
        self, 
        local_dir: str, 
        version: int, 
        progress_callback: Optional[Callable[[str, int, Optional[int]], None]] = None
    ) -> str:
        prefix = f"finetuned/v{version}"
        if not self._configured:
            print(f"[azure_blob] Not configured — skipping HF model upload (prefix: {prefix}/)")
            return prefix

        local = Path(local_dir)
        cc = self._container_client(create_if_missing=True)
        files = [f for f in local.rglob("*") if f.is_file()]
        print(f"[azure_blob] Uploading HF model ({len(files)} files) → {self._container}/{prefix}/")
        _RETRY_DELAYS = [30, 60, 120, 240]
        failed: list[str] = []

        for f in files:
            rel = f.relative_to(local)
            blob_name = f"{prefix}/{rel.as_posix()}"
            size_mb = f.stat().st_size // 1_000_000
            print(f"[azure_blob]   {rel} ({size_mb} MB) …")
            last_exc: Exception | None = None
            for attempt in range(1, 6):
                try:
                    blob_client = cc.get_blob_client(blob_name)
                    with open(f, "rb") as fh:
                        hook = None
                        if progress_callback:
                            hook = lambda current, total: progress_callback(rel.as_posix(), current, total)
                        blob_client.upload_blob(
                            fh, 
                            overwrite=True, 
                            max_concurrency=2,
                            progress_hook=hook
                        )
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < 5:
                        import random
                        wait = _RETRY_DELAYS[min(attempt - 1, len(_RETRY_DELAYS) - 1)]
                        wait += random.randint(0, 15)
                        print(f"[azure_blob]   Retry {attempt}/5 for {rel} (waiting {wait}s): {exc}")
                        time.sleep(wait)
                    else:
                        print(f"[azure_blob]   Retry 5/5 for {rel}: {exc}")
            if last_exc is not None:
                failed.append(str(rel))
                print(f"[azure_blob]   FAILED after 5 attempts: {rel} — {last_exc}")

        if failed:
            raise RuntimeError(
                f"[azure_blob] {len(failed)} file(s) failed to upload to {prefix}. "
                f"Failed files: {', '.join(failed)}"
            )

        # Mark as latest only after all files uploaded successfully
        cc.get_blob_client("finetuned/latest.txt").upload_blob(
            str(version).encode(), overwrite=True
        )
        print(f"[azure_blob] HF model uploaded. Latest → v{version}")
        return prefix

    def get_latest_finetuned_version(self) -> Optional[int]:
        if not self._configured:
            return None
        try:
            blob = self._container_client().get_blob_client("finetuned/latest.txt")
            data = blob.download_blob(timeout=10).readall()
            return int(data.decode().strip())
        except Exception as exc:
            print(f"[azure_blob] Warning: Could not fetch latest version: {exc}")
            return None

    def download_finetuned_model(
        self, 
        version: int, 
        local_dir: str,
        progress_callback: Optional[Callable[[str, int, Optional[int]], None]] = None
    ) -> str:
        if not self._configured:
            raise RuntimeError("AZURE_BLOB_ACCOUNT_URL not configured — cannot download model")

        prefix = f"finetuned/v{version}/"
        local = Path(local_dir)
        local.mkdir(parents=True, exist_ok=True)

        cc = self._container_client()

        # Connectivity pre-check
        try:
            next(iter(cc.list_blobs(name_starts_with=prefix, results_per_page=1)), None)
        except Exception as exc:
            raise RuntimeError(
                f"[azure_blob] Cannot reach Azure Blob at {self._account_url} "
                f"(container={self._container}): {exc}"
            ) from exc

        # Longer retry delays for large shard files (each is ~5 GB).
        _RETRY_DELAYS = [15, 30, 60, 120]
        _CHUNK_BYTES   = 8 * 1024 * 1024   # stream in 8 MB chunks to avoid timeout
        total = 0

        for blob_props in cc.list_blobs(name_starts_with=prefix):
            blob_name = blob_props["name"]
            rel = blob_name[len(prefix):]
            if not rel:
                continue
            dest = local / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            file_size = blob_props.get("size") or 0
            size_mb = file_size // 1_000_000
            print(f"[azure_blob] Downloading {rel} ({size_mb} MB) …")

            last_exc: Exception | None = None
            for attempt in range(1, 6):
                try:
                    blob_client = cc.get_blob_client(blob_name)
                    # Use chunked iteration instead of .readinto() so each
                    # 8 MB chunk has its own timeout window — prevents
                    # ServiceResponseTimeoutError on large (~5 GB) shards.
                    downloader = blob_client.download_blob(max_concurrency=4)
                    downloaded = 0
                    with open(dest, "wb") as fh:
                        for chunk in downloader.chunks():
                            fh.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                progress_callback(rel, downloaded, file_size or None)
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < 5:
                        import random
                        wait = _RETRY_DELAYS[min(attempt - 1, len(_RETRY_DELAYS) - 1)]
                        wait += random.randint(0, 10)
                        print(
                            f"[azure_blob]   Retry {attempt}/5 for {rel} in {wait}s "
                            f"({type(exc).__name__}: {exc})"
                        )
                        time.sleep(wait)
                    else:
                        print(f"[azure_blob]   All 5 attempts failed for {rel}: {exc}")
            if last_exc is not None:
                raise last_exc
            total += 1

        print(f"[azure_blob] Downloaded {total} files → {local_dir}")
        return local_dir

    # ── Quantized GGUF ────────────────────────────────────────────────────────

    def upload_quantized(
        self, 
        gguf_dir: str, 
        version: int,
        progress_callback: Optional[Callable[[str, int, Optional[int]], None]] = None
    ) -> List[str]:
        prefix = f"quantized/v{version}"
        local = Path(gguf_dir)
        keys: List[str] = []

        if not self._configured:
            print(f"[azure_blob] Not configured — skipping quantized upload (prefix: {prefix}/)")
            return keys

        cc = self._container_client(create_if_missing=True)
        files = list(local.glob("*.gguf")) + list(local.glob("manifest.json"))
        print(f"[azure_blob] Uploading {len(files)} quantized file(s) → {self._container}/{prefix}/")
        _RETRY_DELAYS = [30, 90]
        failed: list[str] = []

        for f in sorted(files):
            blob_name = f"{prefix}/{f.name}"
            size_mb = f.stat().st_size // 1_000_000
            print(f"[azure_blob]   {f.name} ({size_mb} MB) …")
            last_exc: Exception | None = None
            for attempt in range(1, 4):
                try:
                    with open(f, "rb") as fh:
                        hook = None
                        if progress_callback:
                            hook = lambda current, total: progress_callback(f.name, current, total)
                        cc.get_blob_client(blob_name).upload_blob(
                            fh, 
                            overwrite=True, 
                            max_concurrency=2,
                            progress_hook=hook
                        )
                    last_exc = None
                    keys.append(blob_name)
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < 3:
                        wait = _RETRY_DELAYS[attempt - 1]
                        print(f"[azure_blob]   Retry {attempt}/3 for {f.name} (waiting {wait}s): {exc}")
                        time.sleep(wait)
            if last_exc is not None:
                failed.append(f.name)
                print(f"[azure_blob]   FAILED after 3 attempts: {f.name} — {last_exc}")

        if failed:
            print(f"[azure_blob] WARNING: {len(failed)} GGUF file(s) failed to upload: {', '.join(failed)}")
        else:
            print(f"[azure_blob] Quantized upload complete ({len(keys)} files).")
        return keys

    # ── Legacy helpers ────────────────────────────────────────────────────────

    def upload_gguf(self, local_path: Path, adapter_id: str, version: str) -> str:
        blob_name = f"adapters/{adapter_id}/{version}/{local_path.name}"
        if not self._configured:
            print(f"[azure_blob] Not configured — skipping GGUF upload ({local_path.name})")
            return blob_name
        print(f"[azure_blob] Uploading {local_path} → {self._container}/{blob_name} …")
        with open(local_path, "rb") as fh:
            self._container_client().get_blob_client(blob_name).upload_blob(fh, overwrite=True)
        return blob_name

    def get_sha256(self, blob_name: str) -> Optional[str]:
        if not self._configured:
            return None
        try:
            data = self._container_client().get_blob_client(blob_name).download_blob().readall()
            return hashlib.sha256(data).hexdigest()
        except Exception as exc:
            print(f"[azure_blob] SHA-256 check failed: {exc}")
            return None

    def find_gguf(self, adapter_path: str) -> Optional[Path]:
        p = Path(adapter_path)
        gguf_files = list(p.glob("*.gguf"))
        return gguf_files[0] if gguf_files else None

    # ── Version listing (used by federated job) ───────────────────────────────

    def list_finetuned_versions(self, latest: int, count: int = 10) -> List[int]:
        """Return available version numbers from finetuned/ prefix."""
        cc = self._container_client()
        found: List[int] = []
        for v in range(max(1, latest - count + 1), latest + 1):
            # Stop at first blob — we only need to know the version exists
            hit = next(iter(cc.list_blobs(name_starts_with=f"finetuned/v{v}/", results_per_page=1)), None)
            if hit is not None:
                found.append(v)
        return found or [latest]
