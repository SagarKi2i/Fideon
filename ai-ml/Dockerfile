FROM runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04

WORKDIR /app

# System deps + cloudflared
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git build-essential cmake libgomp1 zstd lshw && \
    mkdir -p --mode=0755 /usr/share/keyrings && \
    curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg | \
        tee /usr/share/keyrings/cloudflare-public-v2.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-public-v2.gpg] \
    https://pkg.cloudflare.com/cloudflared any main" | \
        tee /etc/apt/sources.list.d/cloudflared.list && \
    apt-get update && apt-get install -y cloudflared && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Pre-install Ollama with CUDA libraries baked into the image.
# zstd (extraction) and lshw (GPU detection) are already installed above.
# The install script bundles cuda_v12/cuda_v13 libs in the main tarball so they
# are present in the image regardless of whether a GPU is visible at build time.
# This eliminates the runtime download and the "Ollama not found" delay on pod start.
RUN curl -fsSL https://ollama.com/install.sh | sh && \
    ls /usr/local/lib/ollama/ | grep -q "cuda" && \
    echo "Ollama CUDA libs verified" || echo "WARNING: CUDA libs not found in image"

# FileBrowser (port 8080)
RUN curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash

# Bake all Python dependencies into the image using the exact frozen versions
# from the confirmed working A100 pod. torch 2.7.0 cu124 runs fine on CUDA 12.8.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
        --extra-index-url https://download.pytorch.org/whl/cu124

COPY . .
RUN chmod +x startup.sh setup.sh

EXPOSE 8000 8080 8188 8888

ENV PYTHONUNBUFFERED=1

CMD ["/bin/bash", "-c", "/app/startup.sh & /start.sh"]
