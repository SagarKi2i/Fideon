import os, json, hashlib, boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig
from supabase import create_client


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "config.env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()



def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["SEAWEEDFS_ENDPOINT"],
        aws_access_key_id=os.environ["SEAWEEDFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["SEAWEEDFS_SECRET_KEY"],
        config=Config(
            signature_version="s3v4",
            connect_timeout=30,
            read_timeout=600,       # 10 min read timeout for large files
            retries={"max_attempts": 1},
        ),
    )


def preflight_check(s3, bucket, endpoint):
    """Verify SeaweedFS bucket exists and is writable before touching large files."""
    print(f"Pre-flight: checking SeaweedFS at {endpoint} ...")

    # 1. Does the bucket exist?
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"  ✓ Bucket '{bucket}' exists")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("404", "NoSuchBucket", "403"):
            raise RuntimeError(
                f"\n  ✗ Bucket '{bucket}' not found or not accessible.\n"
                f"    Run this first:  python3 /app/init_seaweedfs.py\n"
                f"    That will create the bucket and run a connectivity test."
            )
        raise RuntimeError(f"\n  ✗ Cannot reach SeaweedFS: {e}")

    # 2. Can we write to it?
    test_key = "_preflight/write_test.txt"
    try:
        s3.put_object(Bucket=bucket, Key=test_key, Body=b"preflight-ok")
        s3.delete_object(Bucket=bucket, Key=test_key)
        print(f"  ✓ Write test passed")
    except Exception as e:
        raise RuntimeError(
            f"\n  ✗ SeaweedFS write test failed: {e}\n"
            f"\n  Possible causes:\n"
            f"    1. No volume servers are available (disk full or volume server down)\n"
            f"    2. Wrong access/secret key in config.env\n"
            f"    3. SeaweedFS filer is not running on the VM\n"
            f"\n  Check on the VM:  df -h  (disk space)  and  ps aux | grep weed"
        )


def upload_with_multipart(s3, local_path, bucket, remote_key, chunk_mb=32):
    """
    Upload using multipart with small chunks.
    SeaweedFS handles individual parts fine; issues are with very large single PUTs.
    """
    file_size = os.path.getsize(local_path)
    chunk_size = chunk_mb * 1024 * 1024

    if file_size <= chunk_size:
        # Small enough for single PUT
        with open(local_path, "rb") as f:
            s3.put_object(Bucket=bucket, Key=remote_key, Body=f)
        return

    print(f"  Using multipart upload ({chunk_mb}MB chunks, {file_size // chunk_size + 1} parts)...")

    mpu = s3.create_multipart_upload(Bucket=bucket, Key=remote_key)
    upload_id = mpu["UploadId"]
    parts = []

    try:
        with open(local_path, "rb") as f:
            part_num = 1
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                resp = s3.upload_part(
                    Bucket=bucket, Key=remote_key,
                    UploadId=upload_id, PartNumber=part_num, Body=data
                )
                parts.append({"PartNumber": part_num, "ETag": resp["ETag"]})
                pct = f.tell() * 100 // file_size
                print(f"  Part {part_num} uploaded ({pct}%)", end="\r")
                part_num += 1

        s3.complete_multipart_upload(
            Bucket=bucket, Key=remote_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
        print(f"  Multipart upload complete ({part_num - 1} parts)   ")

    except Exception as e:
        s3.abort_multipart_upload(Bucket=bucket, Key=remote_key, UploadId=upload_id)
        raise RuntimeError(f"Multipart upload failed and was aborted: {e}")


def main():
    load_env()
    out_dir   = os.environ["OUTPUT_DIR"]
    bucket    = os.environ["SEAWEEDFS_BUCKET"]
    version   = os.environ["MODEL_VERSION"]
    domain    = os.environ["DOMAIN"]
    endpoint  = os.environ["SEAWEEDFS_ENDPOINT"]

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)

    s3       = s3_client()
    supabase = create_client(os.environ["SUPABASE_URL"],
                             os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    # ── Pre-flight: verify connectivity and write access ─────────────────────
    preflight_check(s3, bucket, endpoint)

    for art in manifest["artifacts"]:
        local_path = os.path.join(out_dir, art["filename"])
        sig_path   = os.path.join(out_dir, art["sig_file"])
        remote_key = f"{domain}/v{version}/{art['filename']}"
        sig_key    = f"{domain}/v{version}/{art['sig_file']}"

        # ── Local pre-flight hash check ──────────────────────────
        local_sha = sha256_file(local_path)
        if f"sha256:{local_sha}" != art["sha256"]:
            raise ValueError(f"Local hash mismatch for {art['filename']} — aborting")

        if not os.path.exists(sig_path):
            raise FileNotFoundError(f"GPG signature missing: {sig_path}")

        # ── Upload GGUF (multipart, 32 MB chunks) ────────────────
        print(f"Uploading {art['filename']} ({art['size_bytes']//1_000_000} MB)...")
        upload_with_multipart(s3, local_path, bucket, remote_key, chunk_mb=32)

        # ── Upload .sig (tiny, single PUT) ───────────────────────
        with open(sig_path, "rb") as f:
            s3.put_object(Bucket=bucket, Key=sig_key, Body=f)

        # ── Server-side size verification (lightweight — avoids re-downloading GBs) ──
        head = s3.head_object(Bucket=bucket, Key=remote_key)
        remote_size = head["ContentLength"]
        if remote_size != art["size_bytes"]:
            s3.delete_object(Bucket=bucket, Key=remote_key)
            s3.delete_object(Bucket=bucket, Key=sig_key)
            raise ValueError(
                f"Remote size mismatch for {art['filename']}: "
                f"expected {art['size_bytes']}, got {remote_size} — deleted"
            )
        print(f"  ✓ Remote size verified ({remote_size // 1_000_000} MB)")

        art["blob_key"] = remote_key

    # ── Upload manifest.json ─────────────────────────────────────────
    with open(manifest_path, "rb") as f:
        s3.put_object(Bucket=bucket, Key=f"{domain}/v{version}/manifest.json", Body=f)
    print("manifest.json uploaded")

    # ── Register in Supabase adapter_registry ───────────────────────
    for art in manifest["artifacts"]:
        supabase.table("adapter_registry").upsert({
            "domain":           domain,
            "adapter_version":  version,
            "filename":         art["filename"],
            "quant_level":      art["quant_level"],
            "sha256":           art["sha256"],
            "size_bytes":       art["size_bytes"],
            "blob_key":         art["blob_key"],
            "min_electron_ver": manifest["min_electron_ver"],
            "canary_pct":       manifest["canary_pct"],
            "rollback_safe":    manifest["rollback_safe"],
            "is_available":     True,
            "blocked":          False,
        }, on_conflict="domain,adapter_version,quant_level").execute()

    print("Upload & registry update complete.")


if __name__ == "__main__":
    main()
