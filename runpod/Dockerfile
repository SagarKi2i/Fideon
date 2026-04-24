# Fideon RunPod PDF Upload Server
# Build:  docker build -t fideon-runpod-upload .
# Run:    docker run -p 8080:8080 -v /workspace/uploads:/workspace/uploads fideon-runpod-upload

FROM python:3.11-slim

WORKDIR /workspace

# Install dependencies
COPY requirements.txt ./runpod/requirements.txt
RUN pip install --no-cache-dir -r runpod/requirements.txt

# Copy server source
COPY server.py ./runpod/server.py
COPY start.sh ./runpod/start.sh
RUN chmod +x /workspace/runpod/start.sh

# Create upload directory
RUN mkdir -p /workspace/uploads

EXPOSE 8080

ENV UPLOAD_DIR=/workspace/uploads
ENV UPLOAD_SERVER_PORT=8080

CMD ["/workspace/runpod/start.sh"]
