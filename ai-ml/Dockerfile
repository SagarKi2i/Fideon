FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# Install cloudflared + build tools (needed by setup.sh at runtime)
RUN apt-get update && apt-get install -y curl git build-essential cmake libgomp1 && \
    mkdir -p --mode=0755 /usr/share/keyrings && \
    curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg | \
    tee /usr/share/keyrings/cloudflare-public-v2.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-public-v2.gpg] \
    https://pkg.cloudflare.com/cloudflared any main" | \
    tee /etc/apt/sources.list.d/cloudflared.list && \
    apt-get update && apt-get install -y cloudflared && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python packages — makes image self-contained for any new pod
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all code
COPY . .

# Permissions
RUN chmod +x startup.sh setup.sh

# Create directories
RUN mkdir -p /workspace/uploads \
             /workspace/fine_tuning/training_samples \
             /workspace/fine_tuning/models \
             /workspace/logs

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["/app/startup.sh"]
