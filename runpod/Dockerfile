# Fideon RunPod PDF Upload + Fine-tuning Server
# NOTE: For pod deployment, upload the runpod/ folder to /workspace/runpod/
#       and run:  bash /workspace/runpod/setup.sh
#
# Build:  docker build -t fideon-runpod .
# Run:    docker run --gpus all -p 8080:8080 \
#           -e SEAWEEDFS_ENDPOINT=... \
#           -e SEAWEEDFS_ACCESS_KEY=... \
#           -e SEAWEEDFS_SECRET_KEY=... \
#           -e SEAWEEDFS_BUCKET=my-bucket \
#           fideon-runpod

FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /workspace

# Install Python dependencies
COPY requirements.txt ./runpod/requirements.txt
RUN pip install --no-cache-dir -r runpod/requirements.txt

# Copy entire runpod package
COPY . ./runpod/

RUN chmod +x /workspace/runpod/start.sh /workspace/runpod/setup.sh

# Build llama.cpp with CUDA (for quantization)
RUN bash /workspace/runpod/setup.sh --skip-pip

# Create data directories
RUN mkdir -p /workspace/uploads \
             /workspace/fine_tuning/training_samples \
             /workspace/fine_tuning/models

EXPOSE 8080

ENV UPLOAD_DIR=/workspace/uploads
ENV UPLOAD_SERVER_PORT=8080

CMD ["/workspace/runpod/start.sh"]
