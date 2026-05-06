import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# Load from backend/.env
load_dotenv("backend/.env")

account_url = os.getenv("AZURE_BLOB_ACCOUNT_URL")
sas_token = os.getenv("AZURE_BLOB_SAS_TOKEN")
container_name = os.getenv("AZURE_BLOB_CONTAINER", "models")

if not account_url or not sas_token:
    print("Error: Azure credentials missing in backend/.env")
    exit(1)

try:
    # Append SAS token to account URL if not already present
    if "?" not in account_url:
        service_url = f"{account_url}?{sas_token}"
    else:
        service_url = account_url

    service_client = BlobServiceClient(account_url=service_url)
    container_client = service_client.get_container_client(container_name)

    print(f"Checking container: {container_name}")
    
    # Check latest.txt
    try:
        blob = container_client.get_blob_client("finetuned/latest.txt")
        latest = blob.download_blob().readall().decode().strip()
        print(f"Latest finetuned version (from latest.txt): v{latest}")
    except Exception:
        print("finetuned/latest.txt not found.")

    # List finetuned versions
    print("\nFinetuned models (finetuned/vN/):")
    blobs = container_client.list_blobs(name_starts_with="finetuned/")
    versions = set()
    for b in blobs:
        parts = b.name.split("/")
        if len(parts) > 1 and parts[1].startswith("v"):
            versions.add(parts[1])
    
    if versions:
        for v in sorted(list(versions)):
            print(f"  - {v}")
    else:
        print("  None found.")

    # List gradients (pending aggregation)
    print("\nGradient updates (gradients/):")
    blobs = container_client.list_blobs(name_starts_with="gradients/")
    gradient_paths = set()
    for b in blobs:
        # Expected: gradients/{model_id}/round-{N}/{device_id}/...
        parts = b.name.split("/")
        if len(parts) >= 4:
            path = "/".join(parts[:4])
            gradient_paths.add(path)
    
    if gradient_paths:
        for p in sorted(list(gradient_paths)):
            print(f"  - {p}")
    else:
        print("  None found.")

except Exception as e:
    print(f"Error connecting to Azure: {e}")
