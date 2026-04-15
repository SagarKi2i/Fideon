"""
init_seaweedfs.py  —  Create the 'models' bucket in local SeaweedFS before
the first pipeline run.

Usage:
    python Quantization/init_seaweedfs.py

Reads credentials from config.env.local (same file the pipeline uses).
Safe to run multiple times — bucket creation is idempotent.
"""

import os
import sys
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def load_env(env_file: str = None) -> None:
    """Load config.env.local (or config.env) into os.environ."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    candidates = [env_file] if env_file else [
        os.path.join(script_dir, "config.env.local"),
        os.path.join(script_dir, "config.env"),
    ]

    for path in candidates:
        if path and os.path.isfile(path):
            print(f"Loading config from: {path}")
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
            return

    print("WARNING: No config.env.local or config.env found — using environment variables only")


def main() -> None:
    load_env()

    endpoint  = os.environ.get("SEAWEEDFS_ENDPOINT", "http://localhost:8333")
    access_key = os.environ.get("SEAWEEDFS_ACCESS_KEY", "localtest")
    secret_key = os.environ.get("SEAWEEDFS_SECRET_KEY", "localtest123")
    bucket    = os.environ.get("SEAWEEDFS_BUCKET",   "models")

    print(f"\nSeaweedFS endpoint : {endpoint}")
    print(f"Bucket             : {bucket}")
    print(f"Access key         : {access_key}")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",   # SeaweedFS ignores region but boto3 requires it
    )

    # ── Check if bucket already exists ──────────────────────────────────────
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"\n✓ Bucket '{bucket}' already exists — nothing to do")
        return
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code not in ("404", "NoSuchBucket"):
            print(f"\n✗ Unexpected error checking bucket: {e}")
            sys.exit(1)

    # ── Create bucket ────────────────────────────────────────────────────────
    print(f"\nCreating bucket '{bucket}'...")
    try:
        s3.create_bucket(Bucket=bucket)
        print(f"✓ Bucket '{bucket}' created successfully")
    except ClientError as e:
        print(f"✗ Failed to create bucket: {e}")
        print("\nMake sure SeaweedFS is running:")
        print("  docker compose -f docker-compose.seaweedfs-local.yml up -d")
        sys.exit(1)

    # ── Quick round-trip test ────────────────────────────────────────────────
    print("\nRunning round-trip test (upload + download + delete)...")
    test_key = "_init_test/ping.txt"
    test_body = b"seaweedfs-ok"

    s3.put_object(Bucket=bucket, Key=test_key, Body=test_body)
    response = s3.get_object(Bucket=bucket, Key=test_key)
    body = response["Body"].read()
    s3.delete_object(Bucket=bucket, Key=test_key)

    if body == test_body:
        print("✓ Round-trip test passed — SeaweedFS is healthy")
    else:
        print(f"✗ Round-trip test FAILED — expected {test_body!r}, got {body!r}")
        sys.exit(1)

    print(f"\n✓ SeaweedFS is ready. Bucket: '{bucket}' @ {endpoint}")
    print("  You can now run: bash Quantization/run_pipeline.sh")


if __name__ == "__main__":
    main()
