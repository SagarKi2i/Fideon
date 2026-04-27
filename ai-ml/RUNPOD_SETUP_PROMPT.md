# RunPod Pod Setup — Fideon PDF Upload + Surya OCR Server

## Prompt to share with the RunPod assistant

> I need to create a RunPod GPU pod that runs a FastAPI server for:
> 1. Receiving PDF file uploads (stored at `/workspace/uploads/`)
> 2. Running **Surya OCR** on uploaded PDFs (GPU-accelerated text extraction)
>
> The server must:
> - Run on **port 8080** (expose via the RunPod HTTP proxy)
> - Accept `POST /upload` with a multipart/form-data PDF file
> - Accept `POST /process/{upload_id}` to trigger Surya OCR (returns a `job_id` immediately)
> - Accept `GET /process/{job_id}/status` to poll OCR progress and results
> - Accept `GET /health` for liveness checks
>
> Please create a pod with:
> - Template: **RunPod PyTorch 2.2.0** (Python 3.11, CUDA pre-installed)
> - GPU: **RTX 3090 or A100** (Surya OCR needs GPU VRAM ≥ 8 GB)
> - Container Disk: at least **50 GB** (for uploaded PDFs and model weights)
> - Expose **port 8080** via the HTTP proxy
> - Expose **port 22** via TCP (for SSH file transfer)
> - The server files will be uploaded to `/workspace/ai-ml/` via SSH

---

## Files to deploy on the pod

These 5 files from the `ai-ml/` folder in this repo go to `/workspace/ai-ml/` on the pod:

| Local file | Pod path |
|---|---|
| `ai-ml/server.py` | `/workspace/ai-ml/server.py` |
| `ai-ml/surya_runner.py` | `/workspace/ai-ml/surya_runner.py` |
| `ai-ml/requirements.txt` | `/workspace/ai-ml/requirements.txt` |
| `ai-ml/start.sh` | `/workspace/ai-ml/start.sh` |
| `ai-ml/__init__.py` | `/workspace/ai-ml/__init__.py` |

---

## Step-by-Step Setup

### Step 1 — Create the Pod on RunPod Dashboard

1. Go to [runpod.io](https://runpod.io) → **Pods** → **+ Deploy**
2. Choose template: **RunPod Pytorch 2.2.0** (or any CUDA + Python 3.11 image)
3. Under **Customize Deployment**:
   - Set **Container Disk** to **50 GB minimum**
   - Under **Expose HTTP Ports**, add port **8080**
   - Under **Expose TCP Ports**, add port **22** (SSH)
4. Note down the **Pod ID** (e.g. `abc123xyz`)

### Step 2 — Get the HTTP proxy URL for port 8080

After the pod starts:
- Dashboard → your pod → **Connect** → **HTTP Service** → copy the URL for port **8080**
- Looks like: `https://<pod-id>-8080.proxy.runpod.net`
- This is your `RUNPOD_UPLOAD_BASE_URL` — add it to `backend/.env`

### Step 3 — SSH into the Pod

```bash
# Get SSH host and port from Dashboard → your pod → Connect → SSH
ssh root@<ssh-host> -p <ssh-port> -i ~/.ssh/your_key
```

### Step 4 — Upload all 5 server files

Run from your local `d:\Fideon OS\` directory:

```bash
# Create directories on the pod
ssh root@<ssh-host> -p <ssh-port> "mkdir -p /workspace/ai-ml /workspace/uploads"

# Copy all server files
scp -P <ssh-port> ai-ml/server.py        root@<ssh-host>:/workspace/ai-ml/
scp -P <ssh-port> ai-ml/surya_runner.py  root@<ssh-host>:/workspace/ai-ml/
scp -P <ssh-port> ai-ml/requirements.txt root@<ssh-host>:/workspace/ai-ml/
scp -P <ssh-port> ai-ml/start.sh         root@<ssh-host>:/workspace/ai-ml/
scp -P <ssh-port> ai-ml/__init__.py      root@<ssh-host>:/workspace/ai-ml/
```

### Step 5 — Install dependencies on the pod

```bash
ssh root@<ssh-host> -p <ssh-port> "pip install -r /workspace/ai-ml/requirements.txt"
```

> **Note:** `surya-ocr` will download ~2–4 GB of model weights on first run. This is normal.

### Step 6 — Start the server

```bash
ssh root@<ssh-host> -p <ssh-port> \
  "cd /workspace/ai-ml && nohup python -m uvicorn server:app \
    --host 0.0.0.0 --port 8080 --log-level info \
    > /workspace/server.log 2>&1 &"
```

### Step 7 — Verify the server is alive

```bash
# From inside the pod
curl http://localhost:8080/health

# From outside (using proxy URL)
curl https://<pod-id>-8080.proxy.runpod.net/health
```

Expected response:
```json
{
  "status": "ok",
  "upload_dir": "/workspace/uploads",
  "total_uploads": 0,
  "total_jobs": 0,
  "disk_files": 0
}
```

### Step 8 — Add env vars to `backend/.env`

```env
# RunPod upload + OCR server (port 8080 proxy URL from Step 2)
RUNPOD_UPLOAD_BASE_URL=https://<pod-id>-8080.proxy.runpod.net

# RunPod pod management
RUNPOD_POD_ID=<your-pod-id>
RUNPOD_API_KEY=<your-runpod-api-key>
```

### Step 9 — (Optional) Auto-start on pod restart

Create `/workspace/start_backend.sh` on the pod:

```bash
#!/bin/bash
mkdir -p /workspace/uploads
cd /workspace
nohup python -m uvicorn server:app \
  --host 0.0.0.0 --port 8080 --log-level info \
  > /workspace/server.log 2>&1 &
```

Then add to `backend/.env`:
```env
RUNPOD_SSH_ENABLED=true
RUNPOD_SSH_HOST=<ssh-host>
RUNPOD_SSH_PORT=<ssh-port>
RUNPOD_REMOTE_START_SCRIPT=/workspace/start_backend.sh
```

The Fideon orchestrator will SSH and run this script automatically when the pod wakes from sleep.

---

## Pod API Endpoints (all on port 8080)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/readyz` | Readiness check |
| `POST` | `/upload` | Upload a PDF (multipart/form-data) |
| `GET` | `/upload/{upload_id}/status` | Poll upload record |
| `GET` | `/uploads` | List all uploads |
| `POST` | `/process/{upload_id}` | Start Surya OCR job → returns `job_id` |
| `GET` | `/process/{job_id}/status` | Poll OCR status + results |
| `GET` | `/jobs` | List all OCR jobs |

---

## Environment Variables Summary

| Variable | Where set | Description |
|---|---|---|
| `RUNPOD_UPLOAD_BASE_URL` | `backend/.env` | `https://<pod-id>-8080.proxy.runpod.net` |
| `RUNPOD_POD_ID` | `backend/.env` | Pod ID from RunPod dashboard |
| `RUNPOD_API_KEY` | `backend/.env` | RunPod API key (Settings → API Keys) |
| `UPLOAD_DIR` | pod env | Where PDFs are stored (default `/workspace/uploads`) |
| `UPLOAD_SERVER_PORT` | pod env | Server port (default `8080`) |
| `OCR_WORKERS` | pod env | Concurrent OCR jobs (default `1`, matches GPU count) |

---

## Testing the Full Flow

Once everything is set up, open the Fideon frontend → **ACORD Form Understanding** tab:

1. Select ACORD form type and pick a **scanned PDF**
2. Click **"Upload PDF to RunPod"** → badge shows `uploaded`
3. Click **"Execute — Run Surya OCR"**
4. Watch the live status steps:
   - `Queued`
   - `Loading Surya model…` *(first run downloads weights — ~2 min)*
   - `Surya is processing…`
   - `Completed ✓`
5. **Extracted Fields** tab shows key-value pairs detected from the PDF
6. **Raw Text** tab shows the full OCR output

Verify directly on RunPod:
```bash
# List all jobs
curl https://<pod-id>-8080.proxy.runpod.net/jobs

# Poll a specific job
curl https://<pod-id>-8080.proxy.runpod.net/process/<job_id>/status
```
