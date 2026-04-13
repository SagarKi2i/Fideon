import os, json, hashlib, boto3
from botocore.config import Config
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


def sha256_stream(body) -> str:
    """Hash a boto3 streaming body without writing to disk."""
    h = hashlib.sha256()
    for chunk in body.iter_chunks(chunk_size=65536):
        h.update(chunk)
    return h.hexdigest()


def s3_client():
    # signature_version="s3v4" is REQUIRED for SeaweedFS — do not omit
    return boto3.client(
        "s3",
        endpoint_url=os.environ["SEAWEEDFS_ENDPOINT"],
        aws_access_key_id=os.environ["SEAWEEDFS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["SEAWEEDFS_SECRET_KEY"],
        config=Config(signature_version="s3v4"),
    )


def main():
    load_env()
    out_dir  = os.environ["OUTPUT_DIR"]
    bucket   = os.environ["SEAWEEDFS_BUCKET"]
    version  = os.environ["MODEL_VERSION"]
    domain   = os.environ["DOMAIN"]

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)

    s3       = s3_client()
    supabase = create_client(os.environ["SUPABASE_URL"],
                             os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    for art in manifest["artifacts"]:
        local_path = os.path.join(out_dir, art["filename"])
        sig_path   = os.path.join(out_dir, art["sig_file"])
        remote_key = f"{domain}/v{version}/{art['filename']}"
        sig_key    = f"{domain}/v{version}/{art['sig_file']}"

        # ── Local pre-flight hash check ──────────────────────────
        local_sha = sha256_file(local_path)
        if f"sha256:{local_sha}" != art["sha256"]:
            raise ValueError(f"Local hash mismatch for {art['filename']} — aborting")

        # ── Upload GGUF and .sig ─────────────────────────────────
        if not os.path.exists(sig_path):
            raise FileNotFoundError(f"GPG signature missing: {sig_path} — was sign_file() called?")
        print(f"Uploading {art['filename']} ({art['size_bytes']//1_000_000} MB)...")
        s3.upload_file(local_path, bucket, remote_key,
                       ExtraArgs={"ServerSideEncryption": "AES256"})
        s3.upload_file(sig_path,   bucket, sig_key)

        # ── Server-side integrity verification ───────────────────
        # Stream from SeaweedFS and re-hash — do NOT save to disk
        obj = s3.get_object(Bucket=bucket, Key=remote_key)
        remote_sha = sha256_stream(obj["Body"])
        if remote_sha != local_sha:
            s3.delete_object(Bucket=bucket, Key=remote_key)
            s3.delete_object(Bucket=bucket, Key=sig_key)
            raise ValueError(f"Remote hash mismatch for {art['filename']} — deleted")
        print(f"  ✓ Remote integrity verified")

        # Store object key — presigned URL is generated on demand by the backend
        art["blob_key"] = remote_key

    # ── Upload manifest.json ─────────────────────────────────────────
    s3.upload_file(manifest_path, bucket, f"{domain}/v{version}/manifest.json")
    print("manifest.json uploaded")

    # ── Register in Supabase adapter_registry ───────────────────────
    for art in manifest["artifacts"]:
        supabase.table("adapter_registry").insert({
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
        }).execute()

    print("Upload & registry update complete.")


if __name__ == "__main__":
    main()
