"""
One-time migration: restructure existing Azure Blob weights to match what
AzureBlobClient expects.

Existing layout (wrong):
  models/v24/model-00001-of-00004.safetensors
  models/v24/v24/config.json
  models/v24/v24/tokenizer.json  ...
  (no finetuned/ prefix, no latest.txt)

Target layout:
  models/finetuned/v24/model-00001-of-00004.safetensors
  models/finetuned/v24/config.json
  models/finetuned/v24/tokenizer.json  ...
  models/finetuned/latest.txt  →  "24"

Run on the pod:
  python /workspace/ai-ml/fix_blob_paths.py
"""
import os
import time

ACCOUNT_URL = os.getenv("AZURE_BLOB_ACCOUNT_URL", "https://swtier.blob.core.windows.net").rstrip("/")
SAS_TOKEN   = os.getenv("AZURE_BLOB_SAS_TOKEN",   "sv=2025-11-05&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-06-04T12:54:05Z&st=2026-05-04T04:39:05Z&spr=https&sig=ZVUsGfphbkOQwoyrmx7dv0mb1UR7LeV6N7bMFF97g%2Bo%3D")
CONTAINER   = os.getenv("AZURE_BLOB_CONTAINER",   "models")
VERSION     = 24

def wait_for_copy(blob_client, timeout: int = 120) -> None:
    for _ in range(timeout):
        props = blob_client.get_blob_properties()
        state = props.copy.status if props.copy else "success"
        if state == "success":
            return
        if state == "failed":
            raise RuntimeError(f"Server-side copy failed: {props.copy.status_description}")
        time.sleep(1)
    raise TimeoutError("Server-side copy timed out")

def main() -> None:
    from azure.storage.blob import BlobServiceClient

    svc = BlobServiceClient(account_url=f"{ACCOUNT_URL}?{SAS_TOKEN}")
    cc  = svc.get_container_client(CONTAINER)

    # ── 1. Copy safetensors: v24/model-* → finetuned/v24/model-* ─────────────
    shard_prefix = f"v{VERSION}/model-"
    shards = list(cc.list_blobs(name_starts_with=shard_prefix))
    if not shards:
        print(f"[!] No safetensors found under '{shard_prefix}' — check VERSION or container name.")
    for blob in shards:
        src_url  = f"{ACCOUNT_URL}/{CONTAINER}/{blob['name']}?{SAS_TOKEN}"
        rel      = blob['name'][len(f"v{VERSION}/"):]        # "model-00001-of-00004.safetensors"
        dst_name = f"finetuned/v{VERSION}/{rel}"
        size_gb  = blob['size'] / 1e9
        print(f"  Copying {blob['name']}  ({size_gb:.2f} GB)  →  {dst_name}")
        dst_client = cc.get_blob_client(dst_name)
        dst_client.start_copy_from_url(src_url)
        wait_for_copy(dst_client)

    # ── 2. Copy config/tokenizer: v24/v24/* → finetuned/v24/* ────────────────
    # Strips the accidental double-nesting so HF can load the model directly.
    double_prefix = f"v{VERSION}/v{VERSION}/"
    configs = list(cc.list_blobs(name_starts_with=double_prefix))
    if not configs:
        # Maybe config files are already flat under v24/ (no double nesting)
        flat_prefix = f"v{VERSION}/"
        configs = [b for b in cc.list_blobs(name_starts_with=flat_prefix)
                   if not b['name'].startswith(shard_prefix)]
        double_prefix = flat_prefix

    for blob in configs:
        src_url  = f"{ACCOUNT_URL}/{CONTAINER}/{blob['name']}?{SAS_TOKEN}"
        rel      = blob['name'][len(double_prefix):]          # "config.json", "tokenizer.json" ...
        if not rel:
            continue
        dst_name = f"finetuned/v{VERSION}/{rel}"
        print(f"  Copying {blob['name']}  →  {dst_name}")
        dst_client = cc.get_blob_client(dst_name)
        dst_client.start_copy_from_url(src_url)
        wait_for_copy(dst_client)

    # ── 3. Create finetuned/latest.txt ────────────────────────────────────────
    cc.get_blob_client("finetuned/latest.txt").upload_blob(
        str(VERSION).encode(), overwrite=True
    )
    print(f"\n[ok] finetuned/latest.txt  →  {VERSION}")

    # ── 4. Verify ─────────────────────────────────────────────────────────────
    found = list(cc.list_blobs(name_starts_with=f"finetuned/v{VERSION}/"))
    print(f"[ok] finetuned/v{VERSION}/ contains {len(found)} blobs")
    for b in found:
        print(f"     {b['name']}  ({b['size'] / 1e6:.1f} MB)")

    print("\nDone. Global Update can now find and aggregate v24.")

if __name__ == "__main__":
    main()
